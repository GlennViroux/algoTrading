#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import glob
import os
import pytz
from yahoo_scraping import YahooScraper
from ticker_alpha import Alpha
import utils
from yahoo_api import YahooAPI
from datetime import datetime,timedelta
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import shutil
import urllib.request as request
from contextlib import closing
'''
ERROR_MODE="ERROR                -:-"
HARDSELL_MODE="HARDSELL             -:-"
APIKEY="KOB33KN2G0O9X8SX"
MAX_TIME_DIFF=timedelta(days=6)
MAX_STOCKS=10
PREV_STOCKS_CHECKED=15
ALPHA_INTRADAY_INTERVAL='30min'
ALPHA_EMA_INTERVAL='30min'
'''

def get_latest_data(ticker,exchange,config_params,logger):
    #FUNCTION='get_latest_data'
    '''
    Description
    '''
    yah=YahooAPI()

    start_day=utils.get_start_business_date(exchange,config_params['trade_logic']['yahoo_period_historic_data'],logger)
    days_in_past=(datetime.now(pytz.timezone('UTC'))-start_day).days+1

    start=datetime.strftime(datetime.now()-timedelta(days=days_in_past),'%Y/%m/%d-%H:%M:%S')
    end=datetime.strftime(datetime.now(),'%Y/%m/%d-%H:%M:%S')

    df_data=yah.get_data(ticker,start,end,config_params['trade_logic']['yahoo_interval'],config_params['trade_logic']['yahoo_period_small_EMA'],config_params['trade_logic']['yahoo_period_big_EMA'],logger=logger)

    return df_data

def get_latest_prices(stock,data):
        #FUNCTION='get_latest_values'
        '''
        returns tuple: (timestamp_data,price_to_sell,price_to_buy,price_current_value)
        '''
        timestamp=datetime.strftime(data['timestamps'][-1],"%Y/%m-%d %H:%M:%S")
        price_to_buy=round(data['high'][-1],2)
        price_to_sell=round(data['low'][-1],2)
        price_current_value=round((data['open'][-1]+data['close'][-1])/2,2)

        return (timestamp,price_to_sell,price_to_buy,price_current_value)

class Stocks:
    def __init__(self,
                balance=0,
                bought_stocks={},
                monitored_stocks=[],
                monitored_stock_data={},
                archive=[],
                current_status={}):
        '''
        balance : current balance. I.e. money in account ready to spend.
        bought stocks : { ticker : (number of stocks in possesion , money spent when buying the stocks)}    
        monitored stocks : [stock1,stock2,...]    
        monitored stock data: 
            {'ticker' : 
                {
                    'timestamps':[],
                    'open':[],
                    'close':[],
                    'low':[],
                    'high':[],
                    'volume':[],
                    'smallEMA':[],
                    'bigEMA':[]
                }
            }
        current status : 
            {'ticker': 
                {
                "fullname": ""
                "number": ""
                "bought" : ""
                "value_bought" : ""
                "value_current" : ""
                "value_sold" : ""
                "virtual_result" : ""
                "final_result" : ""
                "timestamp_bought" : ""
                "timestamp_sold" : ""
                "market_state" : ""
                "timestamp_updated" : ""
                "description" : ""
                "exchange" : ""
                }
            }   
        archive : 
            [
                {
                    'ticker': ...,
                    'timestamp_bought' : ...,
                    'timestamp_sold' : ...,
                    'net_profit_loss' : ...
                },
                ...
            ]
        '''
        self.balance=balance
        self.bought_stocks=bought_stocks
        self.monitored_stocks=monitored_stocks
        self.monitored_stock_data=monitored_stock_data
        self.archive=archive
        self.current_status=current_status

    def initialize_stocks(self,logger,config_params,update_nasdaq_file=False):
        FUNCTION='initialize_stocks'
        '''
        1) find interesting stocks
        2) initialize data for found list in 1)
        '''
        logger.info("Getting stocks to monitor",extra={'function':FUNCTION})

        # TODO this is only for NASDAQ!
        file='./nasdaqtraded.txt'
        if update_nasdaq_file:
            logger.info("Updating nasdaqtraded file",extra={'function':FUNCTION})
            with closing(request.urlopen('ftp://ftp.nasdaqtrader.com/symboldirectory/nasdaqtraded.txt')) as r:
                with open(file, 'wb') as f:
                    shutil.copyfileobj(r, f)
        
        df=pd.read_csv(file,delimiter='|')
        df.drop(df.tail(1).index,inplace=True)

        tickers=list(df.Symbol)

        scraper=YahooScraper()
        result=[]
        for ticker in tickers[:config_params['trade_logic']['number_of_stocks_to_monitor']]:
            logger.debug("Checking {}".format(ticker),extra={'function':FUNCTION})

            scraper=YahooScraper()
            exchange=scraper.get_exchange(ticker,logger)
            if not exchange:
                logger.error("Ticker {} was skipped because no valid response was received from the get_exchange function.".format(ticker),extra={'function':FUNCTION})
                continue

            df_data=get_latest_data(ticker,exchange,config_params,logger)

            if df_data.empty:
                logger.error("No data was received from the yahooAPI",extra={'function':FUNCTION})
                continue

            big_EMAs=df_data.bigEMA

            if len(big_EMAs)<config_params['trade_logic']['number_of_big_EMAs_threshold']:
                logger.debug("Ticker: {}. There weren't enough bigEMA measurements ({} vs required {}) to make a decision".format(ticker,len(big_EMAs),config_params['trade_logic']['number_of_big_EMAs_threshold']),extra={'function':FUNCTION})
                continue

            D,A=utils.get_deriv_surf(big_EMAs,logger)
            logger.debug("Ticker: {}. Derivative: {} and surface indicator: {}.".format(ticker,D,A),extra={'function':FUNCTION})

            if abs(D)>config_params['trade_logic']['big_EMA_derivative_threshold']:
                logger.debug("Ticker: {}. Derivative is too steep ({} vs required {})".format(ticker,abs(D),config_params['trade_logic']['big_EMA_derivative_threshold']),extra={'function':FUNCTION})
                continue

            if A>config_params['trade_logic']['surface_indicator_threshold']:
                logger.debug("Ticker: {}. Surface indicator is too high ({} vs required {})".format(ticker,A,config_params['trade_logic']['surface_indicator_threshold']),extra={'function':FUNCTION})
                continue

            # TODO implement algorithm to select which stocks to monitor       
            to_monitor=True
            if to_monitor:
                if not ticker in self.monitored_stocks:
                    self.monitored_stocks.append(ticker)

                self.monitored_stock_data[ticker]=df_data.to_dict(orient='list')

                market_state=scraper.check_market_state(ticker,logger=logger)

                if ticker in self.current_status:
                    data=df_data.to_dict(orient='list')
                    latest_prices=get_latest_prices(ticker,data)
                    timestamp_data=latest_prices[0]
                    #price_to_sell=latest_prices[1]
                    #price_to_buy=latest_prices[2]
                    price_current_value=latest_prices[3]
                    number=self.current_status[ticker]["number"]
                    if number=="-":
                        current_value="-"
                    else:
                        current_value=round(price_current_value*number,2)

                    value_bought=self.current_status[ticker]["value_bought"]
                    if value_bought=="-" or number=="-":
                        virtual_result="-"
                    else:
                        virtual_result=round(price_current_value*number-value_bought,2)

                    self.current_status[ticker]["timestamp_updated"]=utils.date_now_flutter()
                    self.current_status[ticker]["timestamp_data"]=timestamp_data
                    self.current_status[ticker]["value_current"]=current_value
                    self.current_status[ticker]["virtual_result"]=virtual_result
                    self.current_status[ticker]["market_status"]=market_state
                else:
                    self.current_status[ticker]={"fullname":scraper.get_fullname(ticker,logger),
                                                "number":"-",
                                                "bought":"NO",
                                                "value_bought":"-",
                                                "value_current":"-",
                                                "value_sold":"-",
                                                "virtual_result":"-",
                                                "final_result":"-",
                                                "timestamp_bought":"-",
                                                "timestamp_sold":"-",
                                                "market_state":market_state,
                                                "timestamp_updated":utils.date_now_flutter(),
                                                "timestamp_data":"-",
                                                "description":scraper.get_description(ticker,logger),
                                                "exchange":exchange}


            logger.debug("Adding {} to the list of stocks to be monitored".format(ticker),extra={'function':FUNCTION})
            result.append(ticker)

        logger.info("Initialized {} stocks".format(len(result)),extra={'function':FUNCTION})
        return True

    def buy_stock(self,stock,money_to_spend,price_to_buy,timestamp_data,logger):
        FUNCTION='buy_stock'

        # TODO check if market is open 

        number_to_buy=round(money_to_spend/price_to_buy,2)
        money_spent=round(number_to_buy*price_to_buy,2)

        self.bought_stocks[stock]=(number_to_buy,money_spent)

        self.current_status[stock]["number"]=number_to_buy
        self.current_status[stock]["bought"]="YES"
        self.current_status[stock]["value_bought"]=money_spent
        self.current_status[stock]["value_current"]=money_spent
        self.current_status[stock]["virtual_result"]=0
        self.current_status[stock]["timestamp_bought"]=utils.date_now_flutter()
        self.current_status[stock]["timestamp_data"]=timestamp_data
        self.current_status[stock]["timestamp_updated"]=utils.date_now_flutter()

        self.balance-=money_spent

        logger.info("${} worth of {} stocks were bought.".format(money_spent,stock),extra={'function':FUNCTION})

    def check_yahoo_latency(self,stock,timestamp,threshold,logger):
        FUNCTION='check_yahoo_latency'

        latest_timestamp=datetime(1970,1,1)
        if isinstance(timestamp,str):
            latest_timestamp=datetime.strptime(timestamp,'%Y/%m/%d-%H:%M:%S')
        else:
            latest_timestamp=timestamp

        latency=latest_timestamp-datetime.now()
        if latency>timedelta(seconds=threshold):
            # latest data from yahoo is not valid anymore
            logger.error("Stock {} was not bought because only outdated information from the yahooAPI was received. Latency of {}s is considered with a threshold of {}s".format(stock,latency.seconds,threshold),extra={'function':FUNCTION})
            return False
            
        return True

    def sell_stock(self,stock,price_to_sell,timestamp_data,logger):
        FUNCTION='sell_stock'

        if not stock in self.bought_stocks:
            logger.error("Trying to sell stocks from {}, but no stocks from this company are owned ATM.".format(stock),extra={'function':FUNCTION})
            return False

        value_bought=self.current_status[stock]["value_bought"]
        current_value=round(self.bought_stocks[stock][0]*price_to_sell,2)
        scraper=YahooScraper()

        new_archive={
            'ticker':stock,
            'fullname':scraper.get_fullname(stock,logger),
            'timestamp_bought':self.current_status[stock]["timestamp_bought"],
            'timestamp_sold':utils.date_now_flutter(),
            'net_profit_loss':current_value-value_bought
        }

        self.bought_stocks.pop(stock)
        self.current_status.pop(stock)
        self.monitored_stock_data.pop(stock)
        self.monitored_stocks.remove(stock)

        self.archive.append(new_archive)

        self.balance+=current_value

        logger.info("All stocks of {} were sold for a total of ${}".format(stock,current_value),extra={'function':FUNCTION})

        return True

    def check_monitored_stock(self,stock,config_params,logger):
        FUNCTION='check_monitored_stock'
        '''
        This function checks in on a stock that is being monitored.
        '''
        scraper=YahooScraper()
        stock_bought=(stock in self.bought_stocks)
        market_state=scraper.check_market_state(stock,logger=logger)
        self.current_status[stock]["market_state"]=market_state
        exchange=self.current_status[stock]["exchange"]

        # TODO update data correctly
        df_data=get_latest_data(stock,exchange,config_params,logger)
        if df_data.empty:
            return False

        data=df_data.to_dict(orient='list')
        latest_prices=get_latest_prices(stock,data)
        timestamp_data=latest_prices[0]
        price_to_sell=latest_prices[1]
        price_to_buy=latest_prices[2]
        price_current_value=latest_prices[3]

        smallEMAs=data['smallEMA']
        bigEMAs=data['bigEMA']

        undervalued=(smallEMAs[-1]<bigEMAs[-1])

        # TODO update current status better (virtual result)
        if market_state=="CLOSED" and config_params['trade_logic']['respect_market_hours']:
            logger.info("No checks were performed because the market for {} is closed.".format(stock),extra={'function':FUNCTION})
            return True

        if stock_bought and undervalued:
            # UPDATE AND PASS
            logger.info("Stock {} is bought and undervalued => update and pass.".format(stock),extra={'function':FUNCTION})
            number_stocks_owned=self.bought_stocks[stock][0]
            value_bought=self.current_status[stock]["value_bought"]

            self.current_status[stock]["value_current"]=round(price_current_value*number_stocks_owned,2)
            self.current_status[stock]["virtual_result"]=round(price_current_value*number_stocks_owned-value_bought,2)
            self.current_status[stock]["timestamp_data"]=timestamp_data
            self.current_status[stock]["timestamp_updated"]=utils.date_now_flutter()

        elif (not stock_bought) and (not undervalued):
            # PASS
            logger.info("Stock {} is not bought and overvalued => pass.".format(stock),extra={'function':FUNCTION})
            pass
        elif (not stock_bought) and undervalued:
            # BUY
            logger.info("Stock {} is not bought and undervalued => buy.".format(stock),extra={'function':FUNCTION})
            mytime=data['timestamps'][-1]
            latency_check=self.check_yahoo_latency(stock,mytime,config_params['trade_logic']['yahoo_latency_threshold'],logger)
            if not latency_check:
                pass

            self.buy_stock(stock,config_params['trade_logic']['money_to_spend'],price_to_buy,timestamp_data,logger)
        elif stock_bought and (not undervalued):
            # SELL
            logger.info("Stock {} is bought and overvalued => sell.".format(stock),extra={'function':FUNCTION})
            mytime=data['timestamps'][-1]
            
            latency_check=self.check_yahoo_latency(stock,mytime,config_params['trade_logic']['yahoo_latency_threshold'],logger)
            if not latency_check:
                pass

            self.sell_stock(stock,price_to_sell,timestamp_data,logger)
        # This next option should never occur.
        else:
            logger.error("Strange combination",extra={'function':FUNCTION})

    def hard_sell_check(self,commands,command_log,config_params,logger):
        FUNCTION='hard_sell_check'
        '''
        This function checks whether the user has ordered to sell certain stocks using the app,
        and sells them.
        '''
        tickers=commands['tickers']
        remove_all_stocks=False
        if "ALLSTOCKS" in tickers:
            remove_all_stocks=True
            tickers=list(self.bought_stocks.keys())

        if not tickers:
            return True

        to_remove=[]
        for ticker in tickers:
            if not ticker in self.current_status or self.current_status[ticker]["bought"]=="NO":
                logger.error("Trying to sell stocks from {}, but no stocks from this company are owned ATM.".format(ticker),extra={'function':FUNCTION})
                to_remove.append(ticker)
                continue

            exchange=self.current_status[ticker]["exchange"]

            df_data=get_latest_data(ticker,exchange,config_params,logger)
            if df_data.empty:
                logger.error("Ticker {}. Unable to obtain latest data, ticker is not sold.".format(ticker),extra={'function':FUNCTION})
                continue

            data=df_data.to_dict(orient='list')
            latest_prices=get_latest_prices(ticker,data)
            timestamp_data=latest_prices[0]
            price_to_sell=latest_prices[1]
            #price_to_buy=latest_prices[2]
            #price_current_value=latest_prices[3]

            data=self.monitored_stock_data[ticker]
            price_to_sell=round(data['low'][-1],2)

            success = self.sell_stock(ticker,price_to_sell,timestamp_data,logger)
            if success:
                to_remove.append(ticker)

        if remove_all_stocks:
            commands['tickers']=[]
        else:
            for ticker in to_remove:
                commands['tickers'].remove(ticker)

        utils.write_json(commands,command_log,logger=logger)

    def plot_monitored_stock_data(self,output_dir_plots,logger):
        FUNCTION='plot_monitored_stock_data'
        '''
        This function plots the evolution of the prices per stock.
        '''
        
        data=self.monitored_stock_data
        for ticker in data:
            df=pd.DataFrame(data[ticker])

            delta=df['timestamps'].iloc[1]-df['timestamps'].iloc[0]
            timestamps=df.timestamps
            delta=timedelta(minutes=1)
            for i in range(len(timestamps)-1):
                if timestamps.iloc[i].date()==timestamps.iloc[i+1].date():
                    delta=timestamps.iloc[i+1]-timestamps.iloc[i]
                    break

            df=df.resample(delta,on='timestamps').last().fillna(np.nan)
            df=df.drop(columns='timestamps').reset_index()

            if df.empty:
                logger.error("No valid data for monitored stock {}".format(ticker),extra={'function':FUNCTION})
                continue

            x_dates=pd.to_datetime(df.timestamps)

            y_close=df.close
            y_smallEMA=df.smallEMA
            y_bigEMA=df.bigEMA

            ax=plt.gca()
            plt.rcParams.update({'axes.titlesize': 20})
            plt.rcParams.update({'axes.titleweight': 'roman'})
            ax.xaxis_date()
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y/%m/%d-%H:%M:%S'))

            plt.xticks(rotation=45)
            plt.grid(True)

            plt.title("Stock data for {}".format(ticker),pad=18)
            plt.ylabel("Stock prices [USD]",labelpad=10)
            
            ax.plot(x_dates,y_close,c='tab:blue',marker=',',alpha=1,linewidth=1.2,label="Closes")
            ax.plot(x_dates,y_smallEMA,c='tab:cyan',marker=',',alpha=1,linewidth=1.2,label="smallEMA")
            ax.plot(x_dates,y_bigEMA,c='tab:purple',marker=',',alpha=1,linewidth=1.2,label="bigEMA")

            ax.legend()

            fig=plt.gcf()
            fig.set_size_inches(15,8)

            file_list=glob.glob(output_dir_plots+"/*{}*.png".format(ticker.upper()))
            for f in file_list:
                os.remove(f)

            plt.tight_layout()
            plt.savefig(output_dir_plots+"/{}_{}.png".format(utils.date_now_filename(),ticker),dpi=400)
            plt.clf()
            plt.cla()
            plt.close()

    def get_overview(self,logger,algo_running="Yes"):
        #FUNCTION='get_overview'
        '''
        This function gets the total overview of the current status, in the following form:
        {timestamp: {   'total_virtual_result':...,
                        'total_final_result':...,
                        'number_of_stocks_owned':...
                    }
        }
        '''
        total_final_result=0
        total_virtual_result=0
        number_of_stocks_monitored=0
        number_of_stocks_owned=0
        data=self.current_status

        for key in data:
            number_of_stocks_monitored+=1
            if data[key]["bought"]=="YES":
                number_of_stocks_owned+=1

            if data[key]['virtual_result']!="-" and data[key]['final_result']=="-":
                total_virtual_result+=float(data[key]['virtual_result'])
            elif data[key]['final_result']!="-":
                total_final_result+=float(data[key]['final_result'])

        result={
            'algorithm_running':algo_running,
            'timestamp':utils.date_now_flutter(),
            'total_virtual_result':round(total_virtual_result,2),
            'total_final_result':round(total_final_result,2),
            'number_of_stocks_owned':number_of_stocks_owned,
            'number_of_stocks_monitored':number_of_stocks_monitored
        }

        return result