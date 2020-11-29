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

class Indicators:
    def __init__(self):
        self.time_diff_bod = 'N/A'
        self.time_diff_eod = 'N/A'
        self.der_bigEMA = 'N/A'

class BackTesting(Stocks):
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

        self.indicators = Indicators()

        self.conf = utils.read_config("./config/config.json")
        self.logger=utils.configure_logger("default","./GLENNY_LOG.txt",self.conf["logging"])
        self.initialize_stocks(start,self.logger,self.conf,number_of_stocks,update_nasdaq_file=False,stocks=stocks)

        self.results = {"stock":[],"bought":[],"price_bought":[],
                        "number":[],"result":[],"start_date":[],"comment":[],
                        "timestamp":[],"sell_criterium":[],"first_sold":[],"first_Pe":[],
                        "first_N":[],"second_sold":[],"second_Pe":[],"second_N":[],
                        "time_diff_bod":[],"time_diff_eod":[],'der_bigEMA':[]}

        self.columns = ["timestamp","stock","result","comment","start_date","bought","first_sold","second_sold",
                        "price_bought","first_Pe","second_Pe","number",
                        "first_N","second_N","time_diff_bod","der_bigEMA","sell_criterium"]

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
        price_bought,
        sold_series,
        params,
        comment):
        FUNCTION="append_result"
        '''
        Append one result to the stack
        '''
        if not sold_series:
            first_sold = 'N/A'
            first_Pe = 'N/A'
            first_N = 'N/A'
            second_sold = 'N/A'
            second_Pe = 'N/A'
            second_N = 'N/A'
            result = 'N/A'
            number = 'N/A'
        if len(sold_series)==1:
            first_sold = sold_series[0][0]
            first_Pe = round(sold_series[0][1],3)
            first_N = round(sold_series[0][2],3)
            second_sold = 'N/A'
            second_Pe = 'N/A'
            second_N = 'N/A'
            result = round((first_Pe-price_bought)*first_N,3)
            number = round(first_N,3)
        elif len(sold_series)==2:
            first_sold = sold_series[0][0]
            first_Pe = round(sold_series[0][1],3)
            first_N = round(sold_series[0][2],3)
            second_sold = sold_series[1][0]
            second_Pe = round(sold_series[1][1],3)
            second_N = round(sold_series[1][2],3)
            result = round((first_Pe-price_bought)*first_N + (second_Pe-price_bought)*second_N,3)
            number = round(first_N+second_N,3)

        stock_field = "=HYPERLINK(\"http://{}:5050/backtesting/{}\",\"{}\")".format(self.ip,stock,stock)
        self.results["timestamp"].append(timestamp)
        self.results["stock"].append(stock_field)
        self.results["start_date"].append(start_date)
        self.results["bought"].append(bought)
        self.results["price_bought"].append(round(price_bought,3))
        self.results["first_sold"].append(first_sold)
        self.results["first_Pe"].append(first_Pe)
        self.results["first_N"].append(first_N)
        self.results["second_sold"].append(second_sold)
        self.results["second_Pe"].append(second_Pe)
        self.results["second_N"].append(second_N)
        self.results["result"].append(result)
        self.results["number"].append(number)
        self.results["comment"].append(comment)
        self.results["sell_criterium"].append(self.sell_criterium)

        self.results["time_diff_bod"].append(self.indicators.time_diff_bod)
        self.results["der_bigEMA"].append(self.indicators.der_bigEMA)
        
        sell_epochs = [first_sold,second_sold]
        sell_epochs = [epoch for epoch in sell_epochs if not isinstance(epoch,str)]

        plot_dir = Path(self.plot_dir)
        plot_dir.mkdir(parents=True,exist_ok=True)
        self.logger.debug(f"Ticker: {stock}, plotting result.",extra={'function':FUNCTION})
        self.plot_stock(stock,df,plot_dir,self.logger,start=start_date,bought=bought,sold_series=sell_epochs)

    def get_df_full(self,df):
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

        # cross -1 means fast stochastic goes under slowstochastic
        # cross +1 means fast stochastic goes over slow stochastic
        diff_fast_slow = df.fast_oscillator-df.slow_oscillator
        diff_fast_slow_series = diff_fast_slow.apply(lambda x : np.sign(x)/2).dropna().diff().rename("cross_fast_slow")

        # cross -1 means close goes under advancedEMA
        # cross +1 means close goes over advancedEMA
        diff_close_advancedEMA = df.close-df.advancedEMA
        diff_close_advancedEMA_series = diff_close_advancedEMA.apply(lambda x : np.sign(x)/2).dropna().diff().rename("cross_close_advancedEMA")

        # cross -1 means advancedEMA goes under smallEMA
        # cross +1 means advancedEMA goes over smallEMA
        diff_advancedEMA_smallEMA = df.advancedEMA-df.smallEMA
        diff_advancedEMA_smallEMA_series = diff_advancedEMA_smallEMA.apply(lambda x : np.sign(x)/2).dropna().diff().rename("cross_advancedEMA_smallEMA")

        # cross -1 means advancedEMA goes under bigEMA
        # cross +1 means advancedEMA goes over bigEMA
        diff_advancedEMA_bigEMA = df.advancedEMA-df.bigEMA
        diff_advancedEMA_bigEMA_series = diff_advancedEMA_bigEMA.apply(lambda x : np.sign(x)/2).dropna().diff().rename("cross_advancedEMA_bigEMA")

        # cross -1 means faststochastic goes under 80%
        # cross +1 means faststochastic goes over 80%
        diff_fast_80 = df.fast_oscillator-80
        diff_fast_80_series = diff_fast_80.apply(lambda x : np.sign(x)/2).dropna().diff().rename("cross_fast_80")

        # finite differences of bigEMA
        der_bigEMA = df.bigEMA.diff().rename("der_bigEMA")

        df_full = pd.concat([
            df,
            diff_EMAs_series,
            diff_close_bEMA_series,
            diff_simpleEMA_bigEMA_series,
            diff_close_advancedEMA_series,
            diff_fast_slow_series,
            diff_advancedEMA_smallEMA_series,
            diff_advancedEMA_bigEMA_series,
            diff_fast_80_series,
            der_bigEMA
            ],axis=1)
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
            df_first_crossing = df[(df.timestamps>=first_crossing) & (df.timestamps<=(first_crossing+timedelta(minutes=15))) & (df.cross_simpleEMA_bigEMA==-1)]
            if not df_first_crossing.empty:
                return False
            limit = first_crossing+timedelta(minutes=15)
            df_bought = df[df.timestamps>=limit]

            Pi = df_bought.iloc[0].close
            bought = df_bought.iloc[0].timestamps
            #time_diff_crossing = (bought-previous_timestamp).total_seconds()
        elif self.sell_criterium=='advanced':
            df_start = df[df.timestamps>=self.start].set_index('timestamps')
            #Condition 1: close crosses above advancedEMA
            df_bought = df_start[df_start.cross_close_advancedEMA==1]
            if df_bought.empty:
                return False
            
            i=0
            date = df_bought.index[i]
            success=False
            while (not success) and (i<len(df_bought.index)-1):
                df_date = df_start.loc[:date].tail(5)  
                MACD_crosses = df_date.MACD_histo.apply(lambda x : np.sign(x)/2).dropna().diff()
                cond1 = (not MACD_crosses[MACD_crosses.isin([1])].empty)
                cond2 = df_start.loc[date].MACD_histo>0
                cond3 = df_start.loc[date].SAR<df_start.loc[date].low
                if cond1 and cond2 and cond3:
                    success=True
                    break

                i+=1
                date = df_bought.index[i]
            
            if not success:
                return False

            bought = date
            Pi = df_start.loc[bought].close
            
        return Pi,bought

    def get_sell_info(self,df,bought,N):
        '''
        returns: tuple(list of tuples,comment)
        ([(selling time, price when selling, number of stocks sold)],comment)
        '''
        if self.sell_criterium=='EMA':
            df_sold = df[(df.timestamps>bought) & (df.cross_sEMA_bEMA==1)].set_index('timestamps')

            if df_sold.empty:
                return False
            t_sold = df_sold.index[0]
            Pe = df_sold.loc[df_sold.index[0]].close
            comment = "Bought and sold"
            return ([(t_sold,Pe,N)],comment)
        elif self.sell_criterium=='price':
            df_EMAs_cross = df[(df.timestamps>bought) & (df.cross_sEMA_bEMA==1)]
            if df_EMAs_cross.empty:
                EMA_cross_timestamp = bought
            else:
                EMA_cross_timestamp = df_EMAs_cross.iloc[0].timestamps
            df_sold = df[(df.timestamps>bought) & (df.timestamps>=EMA_cross_timestamp) & (df.cross_close_bEMA==-1)] 

            if df_sold.empty:
                return False
            t_sold = df_sold.index[0]
            Pe = df_sold.loc[df_sold.index[0]].close
            comment = "Bought and sold"
            return ([(t_sold,Pe,N)],comment)
        elif self.sell_criterium=='simple':
            df_sold = df[(df.timestamps>bought) & (df.cross_simpleEMA_bigEMA==-1)]

            if df_sold.empty:
                return False
            t_sold = df_sold.index[0]
            Pe = df_sold.loc[df_sold.index[0]].close
            comment = "Bought and sold"
            return ([(t_sold,Pe,N)],comment)
        elif self.sell_criterium=='advanced':
            df_after_bought = df[df.timestamps>=bought].set_index('timestamps')
            timestamps = df[df.timestamps>=bought].timestamps
            diff = timestamps.diff()
            diff_gaps = diff[diff>timedelta(hours=8)]
            if diff_gaps.empty:
                eod_index = timestamps.index[-1]
            else:
                eod_index = diff[diff>timedelta(hours=8)].index[0]-1
            eod_time = timestamps.loc[eod_index]
            Peod = df_after_bought.loc[eod_time].close
            sold_series_eod = (eod_time,Peod,N)

            if df_after_bought.empty:
                return False

            P_bought = df_after_bought.loc[bought].close
            time_first_stop = pd.NaT
            time_first_target = pd.NaT
            result = []

            # Check if first stop is reached
            first_stop = P_bought - 0.01*P_bought
            df_first_stop = df_after_bought[df_after_bought.close<=first_stop]
            if not df_first_stop.empty:
                time_first_stop = df_first_stop.index[0]
            
            # Check if first target is reached
            first_target = P_bought + 0.02*P_bought
            df_first_target = df_after_bought[df_after_bought.close>=first_target]
            if not df_first_target.empty:
                time_first_target = df_first_target.index[0]

            if pd.isnull(time_first_stop) and pd.isnull(time_first_target):
                # target nor stop are ever reached
                comment = "Nor target nor stop are ever reached"
                comment+=" - sold bcs end of day"
                return ([sold_series_eod],comment)
            elif pd.isnull(time_first_stop) and not pd.isnull(time_first_target):
                # stop never reached but target yes
                Pe_first = df_after_bought.loc[time_first_target].close
                N_first = N/2
                if time_first_target>eod_time:
                    comment = "First target reached, but sold by end of day"
                    return ([sold_series_eod],comment)
                result.append((time_first_target,Pe_first,N_first))
            elif not pd.isnull(time_first_stop) and pd.isnull(time_first_target):
                # stop reached, target never reached
                Pe = df_after_bought.loc[time_first_stop].close
                comment = "Stop reached, but target never reached"
                if time_first_stop<eod_time:
                    return ([(time_first_stop,Pe,N)],comment)
                else:
                    comment+=" - sold bcs end of day"
                    return ([sold_series_eod],comment)
            else:
                # both target and stop reached
                if time_first_stop<=time_first_target:
                    Pe = df_after_bought.loc[time_first_stop].close
                    comment = "Stop reached earlier than target"
                    if time_first_stop<eod_time:
                        return ([(time_first_stop,Pe,N)],comment)
                    else:
                        comment+=" - sold bcs end of day"
                        return ([sold_series_eod],comment)
                else:
                    if time_first_target>eod_time:
                        comment = "First target before first stop, but sold by end of day"
                        return ([sold_series_eod],comment)
                    Pe_first = df_after_bought.loc[time_first_target].close
                    N_first = N/2
                    result.append((time_first_target,Pe_first,N_first))

            # check second half
            N_second = N/2
            df_after_first = df_after_bought[df_after_bought.index>time_first_target]

            df_breakeven = df_after_first[df_after_first.close<=P_bought-0.02*P_bought]
            df_stop = df_after_first[df_after_first.close<=df_after_first.advancedEMA-0.01*P_bought]
            
            if df_breakeven.empty and df_stop.empty:
                # never sold in second half
                sold = df_after_first.index[-1]
                Pe = df_after_first.loc[sold].close
                comment = "Never sold in second half"
            elif not df_breakeven.empty and df_stop.empty:
                # sold by breakeven
                sold = df_breakeven.index[0]
                Pe = df_breakeven.loc[sold].close
                comment = "Sold by breakeven in second half"
            elif df_breakeven.empty and not df_stop.empty:
                # sold by stop
                sold = df_stop.index[0]
                Pe = df_stop.loc[sold].close
                comment = "Sold by stop in second half"
            else:
                # both breakeven and stop reached
                breakeven = df_breakeven.index[0]
                stop = df_stop.index[0]
                if breakeven<=stop:
                    # sold by breakeven
                    sold = df_breakeven.index[0]
                    Pe = df_breakeven.loc[sold].close  
                    comment = "Sold by breakeven in second half"
                else:
                    # sold by stop
                    sold = df_stop.index[0]
                    Pe = df_stop.loc[sold].close 
                    comment = "Sold by stop in second half"     

            if sold<eod_time:
                result.append((sold,Pe,N_second))
            else:
                comment = "Sold in second half by end of day"
                result.append((sold_series_eod[0],sold_series_eod[1],N_second))

            return (result,comment)
  
        else:
            raise Exception("No valid sell criterium ({}) has been provided. Valid options are EMA, price or simple.".format(self.sell_criterium))

    def get_time_diff_bod(self,df,bought):
        df_before_bought = df[df.timestamps<=bought]
        if df_before_bought.empty:
            return False

        timestamps = df_before_bought.timestamps
        diff = timestamps.diff()
        diff_gaps = diff[diff>timedelta(hours=8)]
        if diff_gaps.empty:
            bod_index = timestamps.index[0]
        else:
            bod_index = diff[diff>timedelta(hours=8)].index[-1]
        bod_time = timestamps.loc[bod_index]

        return (bought-bod_time).total_seconds()

    def get_time_diff_eod(self,df,bought):
        df_after_bought = df[df.timestamps>bought]
        if df_after_bought.empty:
            return False

        timestamps = df_after_bought.timestamps
        diff = timestamps.diff()
        diff_gaps = diff[diff>timedelta(hours=8)]
        if diff_gaps.empty:
            eod_index = timestamps.index[-1]
        else:
            eod_index = diff[diff>timedelta(hours=8)].index[0]
        eod_time = timestamps.loc[eod_index]

        return (bod_time-bought).total_seconds()

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

        self.logger.debug(f"Ticker: {stock}, getting bought df.",extra={'function':FUNCTION})
        df = self.get_df_full(df)
        
        # get accept parameters
        params = AcceptParameters(stock,self.current_status[stock]['exchange'],df,self.conf)

        self.logger.debug(f"Ticker: {stock}, getting buy info.",extra={'function':FUNCTION})
        buy_response = self.get_buy_info(df)
        if not buy_response:
            self.append_result(
                df=df,
                timestamp=utils.date_now(),
                stock=stock,
                start_date=self.start,
                bought='N/A',   
                price_bought=0,
                sold_series=[],
                params=params,
                comment="Never bought")
            return True

        Pi,bought = buy_response
        N = round(min(self.M/Pi,self.M/self.Pavg))

        self.logger.debug(f"Ticker: {stock}, getting time duration since start of day.",extra={'function':FUNCTION})
        time_diff_bod = self.get_time_diff_bod(df,bought)
        if not time_diff_bod:
            return False
        self.indicators.time_diff_bod = time_diff_bod

        self.logger.debug(f"Ticker: {stock}, getting time duration until end of day.",extra={'function':FUNCTION})
        time_diff_eod = self.get_time_diff_eod(df,bought)
        if not time_diff_eod:
            return False
        self.indicators.time_diff_eod = time_diff_eod

        self.logger.debug(f"Ticker: {stock}, getting derivative of bigEMA.",extra={'function':FUNCTION})
        der_bigEMA = float(df[df.timestamps==bought].der_bigEMA)
        self.indicators.der_bigEMA = der_bigEMA

        self.logger.debug(f"Ticker: {stock}, getting drop.",extra={'function':FUNCTION})
        if not params.get_drop(bought,self.logger):
            return False

        self.logger.debug(f"Ticker: {stock}, getting sell info.",extra={'function':FUNCTION})
        sell_info = self.get_sell_info(df,bought,N)

        if not sell_info:
            return False

        sold_series,comment = sell_info
        
        self.logger.debug(f"Ticker: {stock}, appending result.",extra={'function':FUNCTION})
        self.append_result(
            df=df,
            timestamp=utils.date_now(),
            stock=stock,
            start_date=self.start,
            bought=bought,
            price_bought=Pi,
            sold_series=sold_series,
            params=params,
            comment=comment)

        self.logger.debug(f"Ticker: {stock}, calculate result done.",extra={'function':FUNCTION})

    def get_df(self):
        return pd.DataFrame.from_dict(self.results)   

    def update_yql_calls_file(self,duration):
        data = self.yahoo_calls
        data['duration']=duration
        utils.write_json(self.yahoo_calls,self.callsYQL_file)

    def append_csv(self,myfile=None,df=None,columns=None,mode='a'):
        FUNCTION='append_csv'
        self.logger.debug("Appending CSV",extra={'function':FUNCTION})
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

    @classmethod
    def clean_all(cls):
        os.system("rm -rf ./backtesting/*plots*")
        os.system("rm ./backtesting/backtesting_stats.csv")
        os.system("touch ./backtesting/backtesting_stats.csv")
        os.system("rm ./backtesting/backtesting_cumulative.csv")
        os.system("touch ./backtesting/backtesting_cumulative.csv")
        from backtesting import BackTesting
        cls.upload_results()
        cls.upload_stats()

    def get_all_stats(self):
        FUNCTION='get_all_stats'
        '''
        Get statisticks about all data available in the CSV file.
        '''
        '''
        params = {
            'drop_buying':False,
            'EMA_surface_plus':True,
            'EMA_surface_min':False,
            'rel_max_drop_buying':False,
            'max_drop_buying':False,
            'rel_max_jump_buying':False,
            'max_jump_buying':False,
            'duration':False,
            'time_diff_crossing':False
            }
        '''
        params = {
            'time_diff_bod':False,
            'time_diff_eod':False,
            'der_bigEMA':False
        }

        self.logger.info("Get all statistics",extra={"function":FUNCTION})
        methods = ['advanced']
        for method in methods:
            self.logger.info(f"Get statistics for the {method} method",extra={"function":FUNCTION})
            for param in params:
                if param in self.conf['trade_logic']:
                    conf_limit = self.conf['trade_logic'][param]
                else:
                    conf_limit = None

                self.get_stats_param(param,conf_limit,method,params[param])
        
        df = pd.DataFrame.from_dict(self.stats)
        if not df.empty:
            self.append_csv(self.csv_file_stats,df,self.columns_stats,mode='w')

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
        
        




