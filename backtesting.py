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

class BackTesting(Stocks,YahooAPI):
    ACCEPT_PARAMS = ["derivative_factor","surface_factor","EMA_surface_plus","EMA_surface_min","number_of_EMA_crossings","drop_period","latest_drop","support_level"]
    def __init__(self,start,number_of_stocks):
        Stocks.__init__(self,balance=[10000,10000])
        YahooAPI.__init__(self)

        if isinstance(start,str):
            start = datetime.strptime(start,'%Y/%m/%d-%H:%M:%S')
        self.start = start

        self.conf = utils.read_config("./config/config.json")
        self.logger=utils.configure_logger("default","./GLENNY_LOG.txt",self.conf["logging"])
        self.initialize_stocks(start,self.logger,self.conf,number_of_stocks)

        self.results = {"stock":[],"bought":[],"sold":[],"price_bought":[],"price_sold":[],
                        "number":[],"result":[],"derivative_factor":[],"surface_factor":[],
                        "EMA_surface_plus":[],"EMA_surface_min":[],"number_of_EMA_crossings":[],
                        "drop_period":[],"latest_drop":[],"support_level":[],"drop_buying":[],
                        "support_level_buying":[],"start_date":[],"comment":[]}

        self.columns = ['start_date','stock','bought','sold','price_bought','price_sold','number','result',
                    'derivative_factor','surface_factor','EMA_surface_plus','EMA_surface_min',
                    'number_of_EMA_crossings','drop_period','latest_drop','support_level',
                    'drop_buying','comment']

        self.csv_file = "./output/backtesting/backtesting_cumulative.csv"

    def get_daily_YQL_calls(self):
        return self.yahoo_calls['daily_calls']

    def get_hourly_YQL_calls(self):
        return self.yahoo_calls['hourly_calls']

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

        diff = df.smallEMA-df.bigEMA
        diff_sign = diff.apply(lambda x : np.sign(x))
        diff_series = diff_sign-diff_sign.shift(periods=1)
        diff_series = diff_series/2
        diff_series.rename("crossing",inplace=True)

        df = pd.concat([df,diff_series],axis=1)
        df_cross = df[(df.crossing==1) | (df.crossing==-1)]
        df_cross_start = df_cross[df_cross.timestamps>=self.start]

        self.plot_stock(stock,df,"./output/plots/back_plots/",self.logger)

        # Search where small EMA < big EMA
        M = 500
        Pavg = 20
        df_index = df_cross_start[df_cross_start.crossing==-1]
        if df_index.empty:
            # If small EMA never goes below big EMA
            self.results["stock"].append(stock)
            self.results["start_date"].append(self.start)
            self.results["bought"].append('N/A')
            self.results["sold"].append('N/A')
            self.results["price_bought"].append(0)
            self.results["price_sold"].append(0)
            self.results["number"].append(0)
            self.results["result"].append(0)
            self.results["drop_buying"].append(0)
            self.results["support_level_buying"].append(0)
            self.results["comment"].append("Never bought")
            for param in self.ACCEPT_PARAMS:
                self.results[param].append(0)
            return False

        Pi_index = df_index.index.values[0]
        Pi = round(df_cross_start.loc[Pi_index].close,2)
        N = round(min(M/Pi,M/Pavg))
        bought = df_cross_start.loc[Pi_index].timestamps
    
        df_data = df[df.timestamps<bought]
        params = AcceptParameters(stock,self.current_status[stock]['exchange'],df_data,self.conf)
        drop_buying = round(params.get_latest_drop(bought,self.logger),3)
        support_level_buying = round(params.get_support_level(bought),3)

        # df_end is the dataframe between the point where smallEMA goes under bigEMA
        # and the point where smallEMA goes over bigEMA 
        df_end = df_cross_start[(df_cross_start.index>Pi_index) & (df_cross_start.crossing==1)]
        if not df_end.empty:
            support_level = self.current_status[stock]["support_level"]
            df_support = df_end[df_end.close<=support_level]
            if not df_support.empty:
                # stock was sold because it dropped below the initial support level
                sold = df_support.iloc[0].timestamps
                Pe = round(df_support.iloc[0].close,2)
                self.results["stock"].append(stock)
                self.results["start_date"].append(self.start)
                self.results["bought"].append(bought)
                self.results["sold"].append(sold)
                self.results["price_bought"].append(Pi)
                self.results["price_sold"].append(Pe)
                self.results["number"].append(N)
                self.results["result"].append(round(N*(Pe-Pi),2))
                self.results["drop_buying"].append(drop_buying)
                self.results["support_level_buying"].append(support_level_buying)
                self.results["comment"].append("Bought and sold because of support level")
                for param in self.ACCEPT_PARAMS:
                    self.results[param].append(round(self.current_status[stock][param],2))

                return False

        if df_end.empty:
            # small EMA never rises again above big EMA
            Pe = round(df_cross_start.iloc[-1].close,2)
            sold = df_cross_start.iloc[-1].timestamps
            self.results["stock"].append(stock)
            self.results["start_date"].append(self.start)
            self.results["bought"].append(Pi)
            self.results["sold"].append(sold)
            self.results["price_bought"].append(Pi)
            self.results["price_sold"].append(Pe)
            self.results["number"].append(N)
            self.results["result"].append(round(N*(Pe-Pi),2))
            self.results["drop_buying"].append(drop_buying)
            self.results["support_level_buying"].append(support_level_buying)
            self.results["comment"].append("Bought but never sold")
            for param in self.ACCEPT_PARAMS:
                self.results[param].append(round(self.current_status[stock][param],2))

            return False

        Pe = round(df_end.iloc[0].close,2)
        sold = df_end.iloc[0].timestamps
        W = round(N*(Pe-Pi),2)

        self.results["stock"].append(stock)
        self.results["start_date"].append(self.start)
        self.results["bought"].append(bought)
        self.results["sold"].append(sold)
        self.results["price_bought"].append(Pi)
        self.results["price_sold"].append(Pe)
        self.results["number"].append(N)
        self.results["result"].append(W)
        self.results["drop_buying"].append(drop_buying)
        self.results["support_level_buying"].append(support_level_buying)
        self.results["comment"].append("Bought and sold")
        for param in self.ACCEPT_PARAMS:
            self.results[param].append(round(self.current_status[stock][param],2))

    def get_df(self):
        return pd.DataFrame.from_dict(self.results)   

    def append_csv(self):
        header = not os.path.isfile(self.csv_file)
        df = pd.DataFrame.from_dict(self.results) 
        df.to_csv(self.csv_file,mode='a',columns=self.columns,header=header)

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

