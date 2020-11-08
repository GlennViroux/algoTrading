#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from trade_logic import Stocks,AcceptParameters
from yahoo_api import YahooAPI

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime,timedelta
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib import cm
import pandas as pd
import numpy as np
import utils
import os

class BackTesting(Stocks):
    ACCEPT_PARAMS = [
        "derivative_factor","surface_factor","EMA_surface_plus","EMA_surface_min",
        "number_of_EMA_crossings","drop_period","latest_drop","support_level"]

    def __init__(self,start,number_of_stocks,sell_criterium,stocks=[]):
        if not stocks:
            stocks = []

        super().__init__(
            balance=[10000,10000],
            bought_stocks={},
            monitored_stocks=[],
            monitored_stock_data={},
            archive=[],
            current_status={},
            interesting_stocks=[],
            not_interesting_stocks=[],
            yahoo_calls={},
            results={})

        if isinstance(start,str):
            start = datetime.strptime(start,'%Y/%m/%d-%H:%M:%S')
        self.start = start

        self.ip = "192.168.0.14"
        self.M = 500
        self.Pavg = 20
        
        self.sell_criterium = sell_criterium

        self.conf = utils.read_config("./config/config.json")
        self.logger=utils.configure_logger("default","./GLENNY_LOG.txt",self.conf["logging"])
        self.initialize_stocks(start,self.logger,self.conf,number_of_stocks,update_nasdaq_file=False,stocks=stocks)

        self.results = {"stock":[],"bought":[],"sold":[],"price_bought":[],"price_sold":[],
                        "number":[],"result":[],"drop_buying":[],"support_level_start":[],
                        "start_date":[],"comment":[],"timestamp":[],"sell_criterium":[],
                        'rel_max_drop_buying':[],'max_drop_buying':[],'rel_max_jump_buying':[],
                        'max_jump_buying':[],'duration':[]}
        for param in self.ACCEPT_PARAMS:
            self.results[param]=[]

        self.columns = [
            'timestamp','stock','result','comment','start_date','bought','sold','price_bought',
            'price_sold','number','surface_factor','EMA_surface_plus','EMA_surface_min',
            'number_of_EMA_crossings','support_level','sell_criterium','drop_buying',
            'rel_max_drop_buying','max_drop_buying','rel_max_jump_buying','max_jump_buying',
            'duration']

        self.stats = {"param":[],"type":[],"total_result_plot":[],"individual_result_plot":[]}
        self.columns_stats = ['param','type','total_result_plot','individual_result_plot']

        self.csv_file = "./backtesting/backtesting_cumulative.csv"
        self.csv_file_stats = "./backtesting/backtesting_stats.csv"
        self.plot_dir = "./backtesting/back_plots/"
        self.stats_plot_dir = "./backtesting/stats_plots/"
        self.callsYQL_file = "./backtesting/calls_yql.json"

    def append_result(  
        self,
        df,
        timestamp,
        stock,
        start_date,
        bought,
        sold,
        price_bought,
        price_sold,
        number,
        result,
        params,
        support_level_start,
        comment):
        '''
        Append one result to the stack
        '''
        duration = 0
        if isinstance(bought,datetime) and isinstance(sold,datetime):
            duration = (sold-bought).total_seconds()

        stock_field = "=HYPERLINK(\"http://{}:5050/backtesting/{}\",\"{}\")".format(self.ip,stock,stock)
        self.results["timestamp"].append(timestamp)
        self.results["stock"].append(stock_field)
        self.results["start_date"].append(start_date)
        self.results["bought"].append(bought)
        self.results["sold"].append(sold)
        self.results["price_bought"].append(price_bought)
        self.results["price_sold"].append(price_sold)
        self.results["number"].append(number)
        self.results["result"].append(result)
        self.results["drop_buying"].append(params.latest_drop)
        self.results["rel_max_drop_buying"].append(params.rel_max_drop)
        self.results["max_drop_buying"].append(params.max_drop)
        self.results["rel_max_jump_buying"].append(params.rel_max_jump)
        self.results["max_jump_buying"].append(params.max_jump)
        self.results["support_level_start"].append(support_level_start)
        self.results["comment"].append(comment)
        self.results["sell_criterium"].append(self.sell_criterium)
        self.results["duration"].append(duration)
        for param in self.ACCEPT_PARAMS:
            self.results[param].append(self.current_status[stock][param])

        if isinstance(bought,str):
            bought=None
        if isinstance(sold,str):
            sold=None

        plot_dir = Path(self.plot_dir)
        plot_dir.mkdir(parents=True,exist_ok=True)
        self.plot_stock(stock,df,plot_dir,self.logger,start=start_date,bought=bought,sold=sold,support_level=support_level_start)

    def get_df_bought(self,df):
        # cross -1 means smallEMA goes under bigEMA
        # cross +1 means smallEMA goes over bigEMA
        diff_EMAs = df.smallEMA-df.bigEMA
        diff_EMAs_series = diff_EMAs.apply(lambda x : np.sign(x)/2).dropna().diff().rename("cross_sEMA_bEMA")
        # cross -1 means close goes under bigEMA
        # cross +1 means close goes over bigEMA
        diff_close_bEMA = df.close-df.bigEMA
        diff_close_bEMA_series = diff_close_bEMA.apply(lambda x : np.sign(x)/2).dropna().diff().rename("cross_close_bEMA")

        # cross -1 means simpleEMA goes under bigEMA
        # cross +1 means simpleEMA goes over bigEMA
        diff_simpleEMA_bigEMA = df.simpleEMA-df.bigEMA
        diff_simpleEMA_bigEMA_series = diff_simpleEMA_bigEMA.apply(lambda x : np.sign(x)/2).dropna().diff().rename("cross_simpleEMA_bigEMA")

        df_full = pd.concat([df,diff_EMAs_series,diff_close_bEMA_series,diff_simpleEMA_bigEMA_series],axis=1)
        return df_full

    def get_buy_info(self,df):
        if self.sell_criterium=='EMA' or self.sell_criterium=='price':
            df_index = df[(df.timestamps>=self.start) & (df.cross_sEMA_bEMA==-1)]
            if df_index.empty:
                return False

            Pi_index = df_index.index.values[0]
            Pi = round(df.loc[Pi_index].close,2)   
            bought = df.loc[Pi_index].timestamps
        elif self.sell_criterium=='simple':
            df_index = df[(df.timestamps>=self.start) & (df.cross_simpleEMA_bigEMA==1)]
            if df_index.empty:
                return False

            first_crossing = df_index.iloc[0].timestamps
            Pi = round(df_index.iloc[0].close,2)
            df_first_crossing = df[(df.timestamps>=first_crossing) & (df.timestamps<=(first_crossing+timedelta(minutes=15))) & (df.cross_simpleEMA_bigEMA==-1)]
            if df_first_crossing.empty:
                return False
            bought = first_crossing+timedelta(minutes=15)
            df_bought = df[df.timestamps==bought]
            Pi = df_bought.iloc[0].close
            
        return Pi,bought

    def get_sold_df(self,df,bought):
        if self.sell_criterium=='EMA':
            df_sold = df[(df.timestamps>bought) & (df.cross_sEMA_bEMA==1)]
        elif self.sell_criterium=='price':
            df_EMAs_cross = df[(df.timestamps>bought) & (df.cross_sEMA_bEMA==1)]
            if df_EMAs_cross.empty:
                EMA_cross_timestamp = bought
            else:
                EMA_cross_timestamp = df_EMAs_cross.iloc[0].timestamps
            df_sold = df[(df.timestamps>bought) & (df.timestamps>=EMA_cross_timestamp) & (df.cross_close_bEMA==-1)] 
        elif self.sell_criterium=='simple':
            df_sold = df[(df.timestamps>bought) & (df.cross_simpleEMA_bigEMA==-1)]
        else:
            raise Exception("No valid sell criterium ({}) has been provided. Valid options are EMA, price or simple.".format(self.sell_criterium))

        return df_sold


    def check_if_sold_by_support_level(self,support_level,bought,df,df_sold):
        df_support = df[(df.timestamps>=bought) & (df.close<=support_level)]
        if not df_support.empty:
            support_crossing = df_support.iloc[0].timestamps
            if df_sold.empty or support_crossing <= df_sold.iloc[0].timestamps:
                # stock was sold because it dropped below the initial support level
                # before the smallEMA rose above the bigEMA
                Pe = round(df_support.iloc[0].close,2)
                return Pe,support_crossing
        return False

    def check_if_never_sold(self,df,bought,df_sold):
        if df_sold.empty:
            # small EMA never rises again above big EMA
            Pe = round(df.iloc[-1].close,2)
            sold = df.iloc[-1].timestamps
            return Pe,sold
        return False

    def get_sell_info(self,N,Pi,df,bought,df_sold):
        Pe = round(df_sold.iloc[0].close,2)
        sold = df_sold.iloc[0].timestamps
        W = round(N*(Pe-Pi),2)
        return Pe,sold,W

    def calculate_result(self,stock):
        FUNCTION='calculate_result'
        if not stock in self.monitored_stocks:
            return False

        self.logger.info(f"Ticker: {stock}, calculating result.",extra={'function':FUNCTION})

        start_data = self.start - timedelta(days=self.conf['trade_logic']['yahoo_period_historic_data'])
        end_data = start_data + timedelta(days=59)
        if end_data>datetime.now():
            end_data = datetime.now()

        interval = self.conf['trade_logic']['yahoo_interval']
        period_small_EMA = self.conf['trade_logic']['yahoo_period_small_EMA']
        period_big_EMA = self.conf['trade_logic']['yahoo_period_big_EMA']
        df = self.get_data(stock,start_data,end_data,interval,period_small_EMA,period_big_EMA,self.logger)

        if df.empty:
            return False

        df = self.get_df_bought(df)
        
        # get accept parameters
        params = AcceptParameters(stock,self.current_status[stock]['exchange'],df,self.conf)

        buy_response = self.get_buy_info(df)
        if not buy_response:
            self.append_result(
                df=df,
                timestamp=utils.date_now(),
                stock=stock,
                start_date=self.start,
                bought='N/A',
                sold='N/A',
                price_bought=0,
                price_sold=0,
                number=0,
                result=0,
                params=params,
                support_level_start=0,
                comment="Never bought")
            return True

        Pi,bought = buy_response
        N = round(min(self.M/Pi,self.M/self.Pavg))

        if not params.get_drop(bought,self.logger):
            return False

        df_sold = self.get_sold_df(df,bought)
        
        support_level_start = self.current_status[stock]["support_level"]
        support_response = self.check_if_sold_by_support_level(support_level_start,bought,df,df_sold)
        if support_response:
            Pe,support_crossing = support_response
            self.append_result(
                df=df,
                timestamp=utils.date_now(),
                stock=stock,
                start_date=self.start,
                bought=bought,
                sold=support_crossing,
                price_bought=Pi,
                price_sold=Pe,
                number=N,
                result=round(N*(Pe-Pi),2),
                params=params,
                support_level_start=support_level_start,
                comment="Bought and sold because of support level")
            return True

        never_sold_response = self.check_if_never_sold(df,bought,df_sold)
        if never_sold_response:
            Pe,sold = never_sold_response
            self.append_result(
                df=df,
                timestamp=utils.date_now(),
                stock=stock,
                start_date=self.start,
                bought=bought,
                sold=sold,
                price_bought=Pi,
                price_sold=Pe,
                number=N,
                result=round(N*(Pe-Pi),2),
                params=params,
                support_level_start=support_level_start,
                comment="Bought but never sold")
            return True

        Pe,sold,W = self.get_sell_info(N,Pi,df,bought,df_sold)

        self.append_result(
            df=df,
            timestamp=utils.date_now(),
            stock=stock,
            start_date=self.start,
            bought=bought,
            sold=sold,
            price_bought=Pi,
            price_sold=Pe,
            number=N,
            result=W,
            params=params,
            support_level_start=support_level_start,
            comment="Bought and sold")

    def get_df(self):
        return pd.DataFrame.from_dict(self.results)   

    def update_yql_calls_file(self,duration):
        data = self.yahoo_calls
        data['duration']=duration
        utils.write_json(self.yahoo_calls,self.callsYQL_file)

    def append_csv(self,myfile=None,df=None,columns=None,mode='a'):
        if not myfile:
            myfile = self.csv_file
        if not isinstance(df,pd.DataFrame) or df.empty:
            df = pd.DataFrame.from_dict(self.results)
        if not columns:
            columns = self.columns

        header = not os.path.isfile(myfile) or os.stat(myfile).st_size==0 or mode=='w'
        df.to_csv(myfile,mode=mode,columns=columns,header=header,index=False)

    @classmethod
    def upload_results(cls):
        scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

        credentials = ServiceAccountCredentials.from_json_keyfile_name('./config/client_secret.json', scope)
        client = gspread.authorize(credentials)

        spreadsheet = client.open('algoTradingBacktesting')

        if not Path("./backtesting/backtesting_cumulative.csv").is_file():
            return False

        with open("./backtesting/backtesting_cumulative.csv", 'r') as file_obj:
            content = file_obj.read()
            client.import_csv(spreadsheet.id, data=content)

        return True

    @classmethod
    def upload_stats(cls):
        scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

        credentials = ServiceAccountCredentials.from_json_keyfile_name('./config/client_secret.json', scope)
        client = gspread.authorize(credentials)

        spreadsheet = client.open('algoTradingStats')

        if not Path("./backtesting/backtesting_stats.csv").is_file():
            return False

        with open("./backtesting/backtesting_stats.csv", 'r') as file_obj:
            content = file_obj.read()
            client.import_csv(spreadsheet.id, data=content)

        return True

    def get_all_stats(self):
        FUNCTION='get_all_stats'
        '''
        Get statisticks about all data available in the CSV file.
        '''
        params = {
            'drop_buying':False,
            'EMA_surface_plus':True,
            'EMA_surface_min':False,
            'rel_max_drop_buying':False,
            'max_drop_buying':False,
            'rel_max_jump_buying':False,
            'max_jump_buying':False,
            'duration':False
            }

        self.logger.info("Get all statistics",extra={"function":FUNCTION})

        for param in params:
            if param in self.conf['trade_logic']:
                conf_limit = self.conf['trade_logic'][param]
            else:
                conf_limit = None

            self.logger.info("Get statistics for price method",extra={"function":FUNCTION})
            self.get_stats_param(param,conf_limit,'price',params[param])
            self.logger.info("Get statistics for EMA method",extra={"function":FUNCTION})
            self.get_stats_param(param,conf_limit,'EMA',params[param])
            self.logger.info("Get statistics for simple method",extra={"function":FUNCTION})
            self.get_stats_param(param,conf_limit,'simple',params[param])
        
        df = pd.DataFrame.from_dict(self.stats)
        
        self.append_csv(self.csv_file_stats,df,self.columns_stats,mode='w')
        self.upload_stats()

    def get_stats_param(self,name,conf_limit,sell_criterium,upper_threshold=False):
        FUNCTION='get_stats_param'

        self.logger.debug(f"Getting statistics for {name} and sell criterium {sell_criterium}",extra={"function":FUNCTION})
        csv_file = Path(self.csv_file)
        if not csv_file.is_file():
            self.logger.error("CSV file is not valid. Breaking off.",extra={"function":FUNCTION})
            return False

        df = pd.read_csv(csv_file)
        df.start_date = pd.to_datetime(df.start_date)
        df = df[df.sell_criterium==sell_criterium]

        if df.empty or not name in df.columns:
            self.logger.error(f"Error, breaking off ({name}, {sell_criterium})",extra={'function':FUNCTION})
            return False
            
        param_min = df[name].min()
        param_max = df[name].max()
        points = np.linspace(param_min,param_max,num=50)

        total_results = []
        for threshold in points:
            if upper_threshold:
                total_results.append(df[df[name] <= threshold].result.sum())
            else:
                total_results.append(df[df[name] >= threshold].result.sum())
        
        self.stats["param"].append(name)
        self.stats["type"].append(sell_criterium)
        df_total_result = pd.DataFrame(list(zip(points,total_results)),columns=[name,'result'])
        self.plot_statistics_total(df_total_result,name,conf_limit,upper_threshold,sell_criterium)

        df_scatter_results = df[['start_date',name,'result']]
        self.plot_statistics_scatter(df_scatter_results,name,conf_limit,upper_threshold,sell_criterium)

    def plot_statistics_scatter(self,df,name,conf_limit,upper_threshold,sell_criterium):
        fig,ax = plt.subplots(figsize=(10,6),dpi=200)

        viridis = cm.get_cmap('viridis', 12)
        start_dates = pd.unique(df.start_date)
        start_dates.sort()
        first_date = start_dates[0]
        last_date = start_dates[-1]
        total_diff = (last_date-first_date)
        for start_date in start_dates:
            df_start_date = df[df.start_date==start_date]
            #start_datetime = datetime.strptime(start_date,'%Y-%m-%d %H:%M:%S')
            timediff = start_date - first_date
            perc = timediff/total_diff
            total = round(df_start_date.result.sum(),2)
            label = f"{pd.to_datetime(str(start_date)).strftime('%Y/%m/%d')} " + "({0:>5}".format(total) + f", {len(df_start_date)})"
            ax.scatter(df_start_date[name],df_start_date.result,c=[viridis(perc)],s=30,alpha=0.6,label=label)

        title = f"Individual statistics for {name}"
        ylabel = "Individual results [$]"
        plot_dir = Path(self.stats_plot_dir) / 'individual' / sell_criterium
        hyperlink = f"=HYPERLINK(\"http://{self.ip}:5050/backtesting/stats-individual-{sell_criterium}-{name}\",\"{name}\")"
        self.stats["individual_result_plot"].append(hyperlink)

        ax.set_title(title,fontsize='xx-large',)
        ax.set_ylabel(ylabel)
        ax.set_xlabel("{} threshold".format(name))
        ax.legend(loc='upper left',bbox_to_anchor=(1.02,1),ncol=1)
        ax.grid()
        plt.tight_layout()

        plot_dir.mkdir(parents=True,exist_ok=True)
        fig.savefig(plot_dir / f"{name}.png")
        del fig
        plt.close()

    def plot_statistics_total(self,df,name,conf_limit,upper_threshold,sell_criterium):
        fig,ax = plt.subplots(figsize=(10,6),dpi=200)
        
        cols = df.columns
        if conf_limit:
            lower = df[cols[0]].iloc[0]
            upper = df[cols[0]].iloc[-1]
            if not upper_threshold:
                if conf_limit>lower:
                    upper_plot = min(conf_limit,upper)
                    ax.axvspan(xmin=lower,xmax=upper_plot,alpha=0.3,facecolor='tab:red')
                if conf_limit<upper:
                    lower_plot = max(conf_limit,lower)
                    ax.axvspan(xmin=lower_plot,xmax=upper,alpha=0.3,facecolor='tab:green')
            else:
                if conf_limit>lower:
                    upper_plot = min(conf_limit,upper)
                    ax.axvspan(xmin=lower,xmax=upper_plot,alpha=0.3,facecolor='tab:green')
                if conf_limit<upper:
                    lower_plot = max(conf_limit,lower)
                    ax.axvspan(xmin=lower_plot,xmax=upper,alpha=0.3,facecolor='tab:red')

        ax.scatter(df[cols[0]],df[cols[1]],s=30,alpha=0.6)

        title = f"Total statistics for {name}"
        ylabel = "Total result [$]"
        plot_dir = Path(self.stats_plot_dir) / 'total' / sell_criterium
        hyperlink = f"=HYPERLINK(\"http://{self.ip}:5050/backtesting/stats-total-{sell_criterium}-{name}\",\"{name}\")"
        self.stats["total_result_plot"].append(hyperlink)

        fig.suptitle(title,fontsize='xx-large')
        ax.set_ylabel(ylabel)
        ax.set_xlabel("{} threshold".format(name))
        ax.grid()

        plot_dir.mkdir(parents=True,exist_ok=True)
        fig.savefig(plot_dir / f"{name}.png")
        del fig
        plt.close()
        
        




