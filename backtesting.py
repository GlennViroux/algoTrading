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

        self.ip = "192.168.0.14"

        self.conf = utils.read_config("./config/config.json")
        self.logger=utils.configure_logger("default","./GLENNY_LOG.txt",self.conf["logging"])
        self.initialize_stocks(start,self.logger,self.conf,number_of_stocks)

        self.results = {"stock":[],"bought":[],"sold":[],"price_bought":[],"price_sold":[],
                        "number":[],"result":[],"derivative_factor":[],"surface_factor":[],
                        "EMA_surface_plus":[],"EMA_surface_min":[],"number_of_EMA_crossings":[],
                        "drop_period":[],"latest_drop":[],"support_level":[],"drop_buying":[],
                        "support_level_buying":[],"start_date":[],"comment":[],"timestamp":[]}

        self.columns = ['timestamp','stock','result','comment','start_date','bought','sold','price_bought','price_sold','number',
                    'surface_factor','EMA_surface_plus','EMA_surface_min',
                    'number_of_EMA_crossings','latest_drop','support_level',
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
        support_level_buying,
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
        self.results["support_level_buying"].append(support_level_buying)
        self.results["comment"].append(comment)
        for param in self.ACCEPT_PARAMS:
            self.results[param].append(round(self.current_status[stock][param],2))

        if isinstance(bought,str):
            bought=None
        if isinstance(sold,str):
            sold=None

        self.plot_stock(stock,df,"./output/plots/back_plots/",self.logger,start=start_date,bought=bought,sold=sold,support_level=support_level_buying)

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

        diff = df.smallEMA-df.bigEMA
        diff_sign = diff.apply(lambda x : np.sign(x))
        diff_series = diff_sign-diff_sign.shift(periods=1)
        diff_series = diff_series/2
        diff_series.rename("crossing",inplace=True)

        df = pd.concat([df,diff_series],axis=1)
        df_cross = df[(df.crossing==1) | (df.crossing==-1)]
        df_cross_start = df_cross[df_cross.timestamps>=self.start]

        # Search where small EMA < big EMA
        M = 500
        Pavg = 20
        df_index = df_cross_start[df_cross_start.crossing==-1]
        if df_index.empty:
            # If small EMA never goes below big EMA
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
                support_level_buying=0,
                comment="Never bought")
                
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
        if df_end.empty:
            # small EMA never rises again above big EMA
            Pe = round(df_cross_start.iloc[-1].close,2)
            sold = df_cross_start.iloc[-1].timestamps

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
                support_level_buying=support_level_buying,
                comment="Bought but never sold")
            return False

        support_level = self.current_status[stock]["support_level"]
        df_support = df[(df.timestamps>=bought) & (df.close<=support_level)]

        if not df_support.empty:
            support_crossing = df_support.iloc[0].timestamps
            if support_crossing <= df_end.iloc[0].timestamps:
                # stock was sold because it dropped below the initial support level
                # before the smallEMA rose above the bigEMA
                Pe = round(df_support.iloc[0].close,2)
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
                    support_level_buying=support_level_buying,
                    comment="Bought and sold because of support level")

                return False

        Pe = round(df_end.iloc[0].close,2)
        sold = df_end.iloc[0].timestamps
        W = round(N*(Pe-Pi),2)

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
            support_level_buying=support_level_buying,
            comment="Bought and sold")

    def get_df(self):
        return pd.DataFrame.from_dict(self.results)   

    def update_yql_calls_file(self):
        utils.write_json(self.yahoo_calls,self.callsYQL_file)

    def append_csv(self):
        header = not os.path.isfile(self.csv_file) or os.stat(self.csv_file).st_size==0
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


