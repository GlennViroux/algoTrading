#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from trade_logic import Stocks,AcceptParameters
from yahoo_api import YahooAPI

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime,timedelta
from collections import namedtuple
import pandas as pd
import numpy as np
import utils
import os

class BackTesting(Stocks):
    ACCEPT_PARAMS = ["derivative_factor","surface_factor","EMA_surface_plus","EMA_surface_min","number_of_EMA_crossings","drop_period","latest_drop","support_level"]
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

        print("GLENNY monitored stocks: ",len(self.monitored_stocks))

        if isinstance(start,str):
            start = datetime.strptime(start,'%Y/%m/%d-%H:%M:%S')
        self.start = start

        self.ip = "192.168.0.14"
        self.M = 500
        self.Pavg = 20
        
        self.sell_criterium = sell_criterium
        self.cross = 'cross_sEMA_bEMA'
        if sell_criterium=='price':
            self.cross = 'cross_close_bEMA'

        self.conf = utils.read_config("./config/config.json")
        self.logger=utils.configure_logger("default","./GLENNY_LOG.txt",self.conf["logging"])
        self.initialize_stocks(start,self.logger,self.conf,number_of_stocks,update_nasdaq_file=True,stocks=stocks)

        self.results = {"stock":[],"bought":[],"sold":[],"price_bought":[],"price_sold":[],
                        "number":[],"result":[],"derivative_factor":[],"surface_factor":[],
                        "EMA_surface_plus":[],"EMA_surface_min":[],"number_of_EMA_crossings":[],
                        "drop_period":[],"latest_drop":[],"support_level":[],"drop_buying":[],
                        "support_level_start":[],"start_date":[],"comment":[],"timestamp":[],
                        "sell_criterium":[]}

        self.columns = ['timestamp','stock','result','comment','start_date','bought','sold','price_bought','price_sold','number',
                    'surface_factor','EMA_surface_plus','EMA_surface_min',
                    'number_of_EMA_crossings','latest_drop','support_level','sell_criterium',
                    'drop_buying']

        self.csv_file = "./output/backtesting/backtesting_cumulative.csv"
        self.callsYQL_file = "./output/backtesting/calls_yql.json"

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
        drop_buying,
        support_level_start,
        comment):
        '''
        Append one result to the stack
        '''

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
        self.results["drop_buying"].append(drop_buying)
        self.results["support_level_start"].append(support_level_start)
        self.results["comment"].append(comment)
        self.results["sell_criterium"].append(self.sell_criterium)
        for param in self.ACCEPT_PARAMS:
            self.results[param].append(round(self.current_status[stock][param],2))

        if isinstance(bought,str):
            bought=None
        if isinstance(sold,str):
            sold=None

        self.plot_stock(stock,df,"./output/plots/back_plots/",self.logger,start=start_date,bought=bought,sold=sold,support_level=support_level_start)

    def get_df_bought(self,df):
        # cross -1 means smallEMA goes under bigEMA
        diff_EMAs = df.smallEMA-df.bigEMA
        diff_EMAs_series = diff_EMAs.apply(lambda x : np.sign(x)/2).dropna().diff().rename("cross_sEMA_bEMA")
        # cross -1 means close goes under bigEMA
        diff_close_bEMA = df.close-df.bigEMA
        diff_close_bEMA_series = diff_close_bEMA.apply(lambda x : np.sign(x)/2).dropna().diff().rename("cross_close_bEMA")

        df_full = pd.concat([df,diff_EMAs_series,diff_close_bEMA_series],axis=1)
        return df_full

    def get_buy_info(self,df):
        df_index = df[(df.timestamps>=self.start) & (df.cross_sEMA_bEMA==-1)]
        if df_index.empty:
            # If small EMA never goes below big EMA
            return False

        Pi_index = df_index.index.values[0]
        Pi = round(df.loc[Pi_index].close,2)   
        bought = df.loc[Pi_index].timestamps

        return Pi,bought

    def check_if_sold_by_support_level(self,support_level,bought,df):
        if self.sell_criterium=='EMA':
            df_sold = df[(df.timestamps>bought) & (df[self.cross]==1)]
        elif self.sell_criterium=='price':
            df_EMAs_cross = df[(df.timestamps>bought) & (df.cross_sEMA_bEMA==1)]
            if df_EMAs_cross.empty:
                EMA_cross_timestamp = bought
            else:
                EMA_cross_timestamp = df_EMAs_cross.iloc[0].timestamps
            df_sold = df[(df.timestamps>bought) & (df.timestamps>=EMA_cross_timestamp) & (df[self.cross]==1)]
        else:
            raise Exception("No valid sell criterium ({}) has been provided. Valid options are EMA or price.".format(self.sell_criterium))

        df_support = df[(df.timestamps>=bought) & (df.close<=support_level)]
        if not df_support.empty:
            support_crossing = df_support.iloc[0].timestamps
            if df_sold.empty or support_crossing <= df_sold.iloc[0].timestamps:
                # stock was sold because it dropped below the initial support level
                # before the smallEMA rose above the bigEMA
                Pe = round(df_support.iloc[0].close,2)
                return Pe,support_crossing
        return False

    def check_if_never_sold(self,df,bought):
        df_sold = df[(df.timestamps>bought) & (df[self.cross]==1)]
        if df_sold.empty:
            # small EMA never rises again above big EMA
            Pe = round(df.iloc[-1].close,2)
            sold = df.iloc[-1].timestamps
            return Pe,sold
        return False

    def get_sell_info(self,N,Pi,df,bought):
        if self.sell_criterium=='EMA':
            df_sold = df[(df.timestamps>bought) & (df[self.cross]==1)]
        elif self.sell_criterium=='price':
            df_EMAs_cross = df[(df.timestamps>bought) & (df.cross_sEMA_bEMA==1)]
            if df_EMAs_cross.empty:
                EMA_cross_timestamp = bought
            else:
                EMA_cross_timestamp = df_EMAs_cross.iloc[0].timestamps
            df_sold = df[(df.timestamps>bought) & (df.timestamps>=EMA_cross_timestamp) & (df[self.cross]==-1)]
        else:
            raise Exception("No valid sell criterium ({}) has been provided. Valid options are EMA or price.".format(self.sell_criterium))

        Pe = round(df_sold.iloc[0].close,2)
        sold = df_sold.iloc[0].timestamps
        W = round(N*(Pe-Pi),2)
        return Pe,sold,W

    def calculate_result(self,stock):
        if not stock in self.monitored_stocks:
            return False

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
                drop_buying=0,
                support_level_start=0,
                comment="Never bought")
            return True

        Pi,bought = buy_response
        N = round(min(self.M/Pi,self.M/self.Pavg))

        # get accept parameters
        df_data = df[df.timestamps<bought]
        params = AcceptParameters(stock,self.current_status[stock]['exchange'],df_data,self.conf)
        drop_buying = round(params.get_latest_drop(bought,self.logger),3)
        
        support_level_start = self.current_status[stock]["support_level"]
        print("GLENNY support level start: ",support_level_start)
        support_response = self.check_if_sold_by_support_level(support_level_start,bought,df)
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
                drop_buying=drop_buying,
                support_level_start=support_level_start,
                comment="Bought and sold because of support level")
            return True

        never_sold_response = self.check_if_never_sold(df,bought)
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
                drop_buying=drop_buying,
                support_level_start=support_level_start,
                comment="Bought but never sold")
            return True

        Pe,sold,W = self.get_sell_info(N,Pi,df,bought)

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
            drop_buying=drop_buying,
            support_level_start=support_level_start,
            comment="Bought and sold")

    def get_df(self):
        return pd.DataFrame.from_dict(self.results)   

    def update_yql_calls_file(self):
        utils.write_json(self.yahoo_calls,self.callsYQL_file)

    def append_csv(self):
        header = not os.path.isfile(self.csv_file) or os.stat(self.csv_file).st_size==0
        df = pd.DataFrame.from_dict(self.results) 
        df.to_csv(self.csv_file,mode='a',columns=self.columns,header=header,index=False)

    def upload_to_drive(self):
        self.append_csv()

        scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

        credentials = ServiceAccountCredentials.from_json_keyfile_name('./config/client_secret.json', scope)
        client = gspread.authorize(credentials)

        spreadsheet = client.open('algoTradingBacktesting')

        with open('./output/backtesting/backtesting_cumulative.csv', 'r') as file_obj:
            content = file_obj.read()
            client.import_csv(spreadsheet.id, data=content)

    @classmethod
    def refresh_drive(cls):
        scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

        credentials = ServiceAccountCredentials.from_json_keyfile_name('./config/client_secret.json', scope)
        client = gspread.authorize(credentials)

        spreadsheet = client.open('algoTradingBacktesting')

        with open('./output/backtesting/backtesting_cumulative.csv', 'r') as file_obj:
            content = file_obj.read()
            client.import_csv(spreadsheet.id, data=content)


