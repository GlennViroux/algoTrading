#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time as _time
import glob
import os
from yahoo_scraping import YahooScraper
from ticker_alpha import Alpha
import utils
import datetime as _datetime
import pandas as pd
import numpy as _np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ERROR_MODE="ERROR                -:-"
HARDSELL_MODE="HARDSELL             -:-"
APIKEY="KOB33KN2G0O9X8SX"
MAX_TIME_DIFF=_datetime.timedelta(days=6)
MAX_STOCKS=10
PREV_STOCKS_CHECKED=15
MONEY_TO_SPEND=500
ALPHA_INTRADAY_INTERVAL='30min'
ALPHA_EMA_INTERVAL='30min'
YAHOO_LATENCY_THRESHOLD=20


class Stocks:
    def __init__(self,
                balance=0,
                current_stocks={},
                previously_checked_stocks=[],
                bought_stock_data={'ticker':[],'timestamps':[],'bid':[],'ask':[],'bought':[],'EMA_small':[],'EMA_big':[]},
                current_status={},
                tosell=[]):
        '''
        balance : current balance. I.e. money in account ready to spend.
        virtual balance : Money that would be in account if we would sell everything now at the current bidding prices.
        current stocks : { ticker : (number of stocks in possesion , money spent when buying the stocks)}        
        previously checked stocks : list of last stocks we looked into whether they were worth buying or not
        bought stock data : dictionary (for dataframe) with the following columns:
            ticker | timestamp | bid (=open) | ask (=open) | EMA_small | EMA_big | bought (1/0) 
        current status : 
            {'ticker': 
                {
                "fullname": ""
                "number": ""
                "value_bought" : ""
                "value_current" : ""
                "value_sold" : ""
                "virtual_result" : ""
                "final_result" : ""
                "timestamp_bought" : ""
                "timestamp_sold" : ""
                }
            }   
        tosell : 
            ['ticker1','ticker2',...]
        '''
        self.balance=balance
        self.current_stocks=current_stocks
        self.previously_checked_stocks=previously_checked_stocks
        self.bought_stock_data=bought_stock_data
        self.current_status=current_status
        self.tosell=tosell

    @property
    def get_balance(self):
        return self.balance

    @property
    def get_current_stocks(self):
        return self.current_stocks

    @property
    def get_previously_checked_stocks(self):
        return self.previously_checked_stocks

    @property
    def get_bought_stock_data(self):
        return self.bought_stock_data

    def hard_sell_check(self,output_dir_log):
        '''
        This function checks whether the user has ordered to sell certain stocks using the app, 
        and sells them. 
        '''
        if self.tosell:
            remove_all_stocks=False
            command_log=utils.get_latest_log("COMMANDS")
            commands=utils.read_commands(command_log)
            scraper=YahooScraper()
            tickers=self.tosell
            if "ALLSTOCKS" in tickers:
                remove_all_stocks=True
                tickers=list(self.current_stocks.keys())
            to_remove=[]
            for ticker in tickers:
                if not ticker in self.current_stocks:
                    utils.write_output_formatted(HARDSELL_MODE,"Trying to sell stocks from {}, but no stocks from this company are owned ATM.".format(ticker),output_dir_log)
                    to_remove.append(ticker)
                    continue
                    
                number=self.current_stocks[ticker][0]
                
                bid_ask=scraper.get_bid_and_ask(ticker)
                if not bid_ask:
                    utils.write_output_formatted(HARDSELL_MODE,"When checking to sell: no valid response was received from the Yahoo Finance website for the {} stock. Selling all stocks for {}.".format(ticker,ticker),output_dir_log)
                    bid_price=0
                    ask_price=0
                else:
                    bid_price=bid_ask['bid']
                    ask_price=bid_ask['ask']

                utils.write_output_formatted(HARDSELL_MODE,"Selling {} stocks from {} for ${} ...".format(number,ticker,number*bid_price),output_dir_log)
                    
                self.bought_stock_data['ticker'].append(ticker)
                self.bought_stock_data['timestamps'].append(pd.Timestamp.now())
                self.bought_stock_data['bid'].append(bid_price)
                self.bought_stock_data['ask'].append(ask_price)
                self.bought_stock_data['EMA_small'].append(_np.nan)
                self.bought_stock_data['EMA_big'].append(_np.nan)

                self.current_stocks.pop(ticker)
                self.balance+=(number*bid_price)
                self.bought_stock_data['bought'].append(0)
                self.current_status[ticker]['timestamp_updated']=utils.date_now_flutter()
                self.current_status[ticker]["value_sold"]=str(round(number*bid_price,3))
                self.current_status[ticker]["final_result"]=str(round((float(self.current_status[ticker]["value_current"])-float(self.current_status[ticker]["value_bought"]))*number,3))
                self.current_status[ticker]["timestamp_sold"]=utils.date_now()

                self.current_status[ticker]["value_current"]=str(round(self.current_status[ticker]["number"]*ask_price,3))
                self.current_status[ticker]["virtual_result"]="-"

                to_remove.append(ticker)
                

                utils.write_output_formatted(HARDSELL_MODE,"Sold {} stocks from {} for ${}".format(number,ticker,number*bid_price),output_dir_log)
            
            if remove_all_stocks:
                self.tosell=[]
                commands['tickers']=[]
            else:
                for ticker in to_remove:
                    self.tosell.remove(ticker)
                    commands['tickers'].remove(ticker)

            utils.write_json(commands,command_log)


    def get_overview(self):
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
        number_of_stocks_owned=0
        data=self.current_status
        for key in data:
            number_of_stocks_owned+=1
            if data[key]['virtual_result']!="-" and data[key]['final_result']=="-":
                total_virtual_result+=float(data[key]['virtual_result'])
            elif data[key]['final_result']!="-":
                total_final_result+=float(data[key]['final_result'])
        result={'timestamp':utils.date_now_flutter(),'total_virtual_result':round(total_virtual_result,2),'total_final_result':round(total_final_result,2),'number_of_stocks_owned':number_of_stocks_owned}
        return result

    def get_EMA(self,yahooscraper,alpha,ticker,interval,time_period):
        '''
        This function calculates the EMA including the last available price from today.
        '''  
        try:
            last_EMA=alpha.EMA(interval,time_period,'close')
        except RuntimeError:
            return None
        
        ask_price=yahooscraper.get_bid_and_ask(ticker)['ask']
        if not ask_price:
            return None

        EMA_today=ask_price*(2/(1+time_period))+last_EMA*(1-2/(1+time_period))

        return EMA_today

    def get_EMAs(self,yahooscraper,alpha,ticker,interval,time_period):
        '''
        This function provides the EMA timeseries including the last available price from today.
        '''  
        try:
            EMA_df=alpha.EMAs(interval,time_period,'close')
            EMA_dict=EMA_df.to_dict('list')
            timestamps_list=EMA_dict['timestamps']
            EMA_list=EMA_dict['EMA']
            last_EMA=EMA_df.iloc[-1]['EMA']
        except:
            return pd.DataFrame()
        
        bid_and_ask=yahooscraper.get_bid_and_ask(ticker)
        if not bid_and_ask:
            return pd.DataFrame()

        ask_price=bid_and_ask['ask']

        last_EMA_updated=ask_price*(2/(1+time_period))+last_EMA*(1-2/(1+time_period))

        timestamps_list.append(_datetime.datetime.now())
        EMA_list.append(last_EMA_updated)

        return pd.DataFrame({'timestamps':timestamps_list,'EMA':EMA_list})

    def update_bought_stock_data_buying(self,stock,data,df_EMA_small,df_EMA_big,bid_price,ask_price,EMA_small,EMA_big):
        '''
        This function updates the information about stocks bought and sold when buying stocks.
        '''
        df_bought_stock_data=pd.DataFrame(self.bought_stock_data)

        df_EMA_small.rename(columns={'EMA':'EMA_small'},inplace=True)
        df_EMA_big.rename(columns={'EMA':'EMA_big'},inplace=True)

        EMA_small_dict=df_EMA_small.to_dict('list')
        EMA_big_dict=df_EMA_big.to_dict('list')

        EMA_small_dict['timestamps']+=[pd.Timestamp.now()]
        EMA_small_dict['EMA_small']+=[EMA_small]
        EMA_big_dict['timestamps']+=[pd.Timestamp.now()]
        EMA_big_dict['EMA_big']+=[EMA_big]

        df_EMA_small=pd.DataFrame(EMA_small_dict)
        df_EMA_big=pd.DataFrame(EMA_big_dict)

        df_EMA=pd.concat([df_EMA_small.set_index('timestamps'),df_EMA_big.set_index('timestamps')],axis=1,join='outer').reset_index()

        stock_data=pd.DataFrame({'timestamps':[pd.Timestamp.now()]+data['timestamps'].to_list(),
                                    'bid':[bid_price]+data['opens'].to_list(),
                                    'ask':[ask_price]+data['opens'].to_list(),
                                    'bought':[1]+[0 for i in range(len(data))]})

        df_EMA_data = pd.concat([stock_data.set_index('timestamps'),df_EMA.set_index('timestamps')],axis=1,join='outer').reset_index()
        df_EMA_data.insert(0,'ticker',[stock for i in range(len(df_EMA_data))])
        df_EMA_data.reset_index(inplace=True)

        full_df=pd.concat([df_bought_stock_data.set_index('timestamps'),df_EMA_data.set_index('timestamps')],axis=0,join='outer').reset_index()
        full_df.drop(labels="index",axis=1,inplace=True,errors='ignore')

        self.bought_stock_data=full_df.to_dict('list')


    def update_bought_stock_data_selling(self,stock,bid_price,ask_price,EMA_small,EMA_big):
        '''
        This function updates the information about stocks bought and sold when selling stocks.
        '''
        self.bought_stock_data['ticker'].append(stock)
        self.bought_stock_data['timestamps'].append(pd.Timestamp.now())
        self.bought_stock_data['bid'].append(bid_price)
        self.bought_stock_data['ask'].append(ask_price)
        self.bought_stock_data['bought'].append(0)
        self.bought_stock_data['EMA_small'].append(EMA_small)
        self.bought_stock_data['EMA_big'].append(EMA_big)


    def check_to_buy(self,output_dir_log):
        '''
        This function checks out the highest gainer and whether 
        we should buy stocks at this moment.
        '''
        MODE="CHECK TO BUY         -:-"
        scraper=YahooScraper()
        gainers=scraper.get_symbols_best_gainers(20)
        names=scraper.get_names_best_gainers(20)

        if not gainers or not names:
            utils.write_output_formatted(ERROR_MODE,"When checking for best gainers, no valid response was received from the Yahoo Finance website.",output_dir_log)
            return False

        utils.write_output_formatted(MODE,"Best gainers: {}".format(utils.write_stocks(gainers)),output_dir_log)
        utils.write_output_formatted(MODE,"Previously checked stocks: {}".format(self.previously_checked_stocks),output_dir_log)

        gainer=None
        name=None
        cnt=0
        while (gainer==None) or (gainer in self.current_stocks) or (gainer in self.previously_checked_stocks) or (not scraper.check_if_market_open(gainer)):
            # Search until a new stock if found which we haven't bought already or until we find one with a market that is open now
            if cnt>=len(gainers):
                break
            gainer=gainers[cnt]
            name=names[cnt]
            cnt+=1

        if not gainer:
            utils.write_output_formatted(MODE,"No valid stock with an open stock market was found.",output_dir_log)
            return True

        self.previously_checked_stocks.append(gainer)
        self.previously_checked_stocks=self.previously_checked_stocks[-PREV_STOCKS_CHECKED:]

        utils.write_output_formatted(MODE,"Looking to buy {} ({}) stocks...".format(gainer,name),output_dir_log)

        # Check whether we want to buy stocks of the highest gainer
        time_start=_datetime.datetime.now()
        alpha=Alpha(gainer,APIKEY)
        df_EMA_200=self.get_EMAs(scraper,alpha,gainer,ALPHA_EMA_INTERVAL,200)
        df_EMA_20=self.get_EMAs(scraper,alpha,gainer,ALPHA_EMA_INTERVAL,20)

        if df_EMA_20.empty or df_EMA_200.empty:
            utils.write_output_formatted(ERROR_MODE,"When calculating EMAs, no valid response was received from the Yahoo Finance or AlphaVantage website for the {} stock.".format(gainer),output_dir_log)            
            time_stop=_datetime.datetime.now()
            seconds_to_sleep=60-((time_stop-time_start).seconds)
            utils.write_output_formatted(MODE,"Sleeping {}s ...".format(seconds_to_sleep),output_dir_log)
            _time.sleep(seconds_to_sleep)
            return False

        EMA_20=df_EMA_20.iloc[-1]['EMA']
        EMA_200=df_EMA_200.iloc[-1]['EMA']

        if EMA_20 and EMA_200:
            flag1=EMA_20>EMA_200
            utils.write_output_formatted(MODE,"EMA check {}".format(flag1),output_dir_log)
        else:
            utils.write_output_formatted(ERROR_MODE,"EMA check {} (no valid response was received from the AlphaVantage API or Yahoo Finance website for the {} stock.".format(flag1,gainer),output_dir_log)
            time_stop=_datetime.datetime.now()
            seconds_to_sleep=60-((time_stop-time_start).seconds)
            utils.write_output_formatted(MODE,"Sleeping {}s ...".format(seconds_to_sleep),output_dir_log)
            _time.sleep(seconds_to_sleep)
            return False

        flag2=not (gainer in self.current_stocks)
        flag3=len(self.current_stocks)<=MAX_STOCKS

        utils.write_output_formatted(MODE,"already bought check {}".format(flag2),output_dir_log)
        utils.write_output_formatted(MODE,"max stocks bought check {}".format(flag3),output_dir_log)

        if flag1 and flag2 and flag3:
            # Buy stocks for a fixed amount of money
            bid_and_ask=scraper.get_bid_and_ask(gainer)

            if not bid_and_ask:
                utils.write_output_formatted(ERROR_MODE,"When getting bid and ask prices, no valid response was received from the Yahoo Finance website for the {} stock.".format(gainer),output_dir_log)
                time_stop=_datetime.datetime.now()
                seconds_to_sleep=60-((time_stop-time_start).seconds)
                utils.write_output_formatted(MODE,"Sleeping {}s ...".format(seconds_to_sleep),output_dir_log)
                _time.sleep(seconds_to_sleep)
                return False

            try:
                data=alpha.last_data(ALPHA_INTRADAY_INTERVAL,outputsize='full')
            except:
                utils.write_output_formatted(ERROR_MODE,"When getting last data, no valid response was received from the AlphaVantage API for the {} stock.".format(gainer),output_dir_log)
                time_stop=_datetime.datetime.now()
                seconds_to_sleep=60-((time_stop-time_start).seconds)
                utils.write_output_formatted(MODE,"Sleeping {}s ...".format(seconds_to_sleep),output_dir_log)
                _time.sleep(seconds_to_sleep)
                return False

            bid_price=bid_and_ask['bid']
            ask_price=bid_and_ask['ask']
            stocks_to_buy=round(float(MONEY_TO_SPEND/ask_price),3)
            self.current_status[gainer]={"fullname":name,
                                        "number":stocks_to_buy,
                                        "value_bought":str(round(stocks_to_buy*ask_price,3)),
                                        "value_current":str(round(stocks_to_buy*ask_price,3)),
                                        "value_sold":"-",
                                        "virtual_result":"-",
                                        "final_result":"-",
                                        "timestamp_bought":utils.date_now(),
                                        "timestamp_sold":"-",
                                        "market_open":"Yes",
                                        "timestamp_updated":utils.date_now_flutter()}
            self.balance-=stocks_to_buy*ask_price
            self.current_stocks[gainer]=(stocks_to_buy,round(ask_price*stocks_to_buy,3))
            utils.write_output_formatted(MODE,"Buying {} stocks from {} ({}) for ${}".format(stocks_to_buy,gainer,name,round(stocks_to_buy*ask_price,3)),output_dir_log)

            # Save historic stock data for plotting purposes
            
            self.update_bought_stock_data_buying(gainer,data,df_EMA_20,df_EMA_200,bid_price,ask_price,EMA_20,EMA_200)

        else:
            # Don't do anything
            utils.write_output_formatted(MODE,"Not buying {} ({}) stocks.".format(gainer,name),output_dir_log)            

        time_stop=_datetime.datetime.now()
        seconds_to_sleep=60-((time_stop-time_start).seconds)
        utils.write_output_formatted(MODE,"Sleeping {}s ...".format(seconds_to_sleep),output_dir_log)
        _time.sleep(seconds_to_sleep)

        return True

    def check_to_sell(self,output_dir_log):
        '''
        This functions checks whether we should sell any of the 
        stocks we currently hold.
        '''
        MODE="CHECK TO SELL        -:-"

        scraper=YahooScraper()

        # Update first historic stock data for stocks we already sold and are not in our posession anymore
        all_bought_stocks=set(self.bought_stock_data['ticker'])
        old_stocks=all_bought_stocks-set(self.current_stocks.keys())
        for old_stock in old_stocks:
            bid_ask=scraper.get_bid_and_ask(old_stock)
            if not bid_ask:
                utils.write_output_formatted(ERROR_MODE,"When updating historic stock data: no valid response was received from the Yahoo Finance website for the {} stock.".format(old_stock),output_dir_log)
                return False

            bid_price=bid_ask['bid']
            ask_price=bid_ask['ask']
            EMA_20=_np.nan
            EMA_200=_np.nan

            self.update_bought_stock_data_selling(old_stock,bid_price,ask_price,EMA_20,EMA_200)

        stocks_list=list(self.current_stocks.keys())
        for stock in stocks_list:
            if scraper.check_if_market_open(stock)==None:
                self.current_status[stock]["market_open"]="Unknown"
                utils.write_output_formatted(MODE,"Not checking to sell {} stocks, market state is unknown".format(stock),output_dir_log)
                continue
            elif scraper.check_if_market_open(stock)==False:
                self.current_status[stock]["market_open"]="No"
                utils.write_output_formatted(MODE,"Not checking to sell {} stocks, market is closed.".format(stock),output_dir_log)
                continue

            self.current_status[stock]["market_open"]="Yes"

            utils.write_output_formatted(MODE,"Looking to sell {} stocks...".format(stock),output_dir_log)
            time_start=_datetime.datetime.now()

            # Check whether we want to sell the stock
            alpha=Alpha(stock,APIKEY)

            EMA_200=self.get_EMA(scraper,alpha,stock,ALPHA_EMA_INTERVAL,200)
            EMA_20=self.get_EMA(scraper,alpha,stock,ALPHA_EMA_INTERVAL,20)

            if not EMA_20 or not EMA_200:
                utils.write_output_formatted(ERROR_MODE,"EMA check (no valid response was received from the AlphaVantage API or Yahoo Finance website for the {} stock.".format(stock),output_dir_log)
                return False

            flag=EMA_20<=EMA_200
            utils.write_output_formatted(MODE,"EMA check {}".format(flag),output_dir_log)

            # With the current bid and ask prices, update information about stocks in posession
            number=self.current_stocks[stock][0]

            bid_ask=scraper.get_bid_and_ask(stock)
            if not bid_ask:
                utils.write_output_formatted(ERROR_MODE,"When checking to sell: no valid response was received from the Yahoo Finance website for the {} stock. Selling all stocks for {}.".format(stock,stock),output_dir_log)
                flag=True
                bid_price=0
                ask_price=0
            else:
                bid_price=bid_ask['bid']
                ask_price=bid_ask['ask']
                
            self.bought_stock_data['ticker'].append(stock)
            self.bought_stock_data['timestamps'].append(pd.Timestamp.now())
            self.bought_stock_data['bid'].append(bid_price)
            self.bought_stock_data['ask'].append(ask_price)
            self.bought_stock_data['EMA_small'].append(EMA_20)
            self.bought_stock_data['EMA_big'].append(EMA_200)

            self.current_status[stock]["value_current"]=str(round(self.current_status[stock]["number"]*ask_price,3))
            self.current_status[stock]["virtual_result"]=str(round((float(self.current_status[stock]["value_current"])-float(self.current_status[stock]["value_bought"]))*number,3))
            self.current_status[stock]['timestamp_updated']=utils.date_now_flutter()

            if flag:
                # Sell all stocks of the stock we're looking at
                self.current_stocks.pop(stock)
                self.balance+=(number*bid_price)
                self.bought_stock_data['bought'].append(0)
                self.current_status[stock]["value_sold"]=str(round(number*bid_price,3))
                self.current_status[stock]["final_result"]=str(round((float(self.current_status[stock]["value_current"])-float(self.current_status[stock]["value_bought"]))*number,3))
                self.current_status[stock]["virtual_result"]="-"
                self.current_status[stock]["timestamp_sold"]=utils.date_now()
                self.current_status[stock]['timestamp_updated']=utils.date_now_flutter()
                utils.write_output_formatted(MODE,"Selling {} stocks from {} for ${}".format(number,stock,number*bid_price),output_dir_log)
            else:
                # Update historic plot data for plotting purposes
                self.bought_stock_data['bought'].append(1)
                utils.write_output_formatted(MODE,"Not selling {} stocks.".format(stock),output_dir_log)

            time_stop=_datetime.datetime.now()
            seconds_to_sleep=60-((time_stop-time_start).seconds)
            utils.write_output_formatted(MODE,"Sleeping {}s ...".format(seconds_to_sleep),output_dir_log)
            _time.sleep(seconds_to_sleep)
        
    def plot_bought_stock_data(self,output_dir_plots):
        '''
        This function plots the evolution of the prices per stock, showing also when a stock
        was bought and when it was sold.
        '''
        df=pd.DataFrame(self.bought_stock_data)
        #df.dropna(thresh=3,inplace=True)
        tickers=df.ticker.unique()
        
        for ticker in tickers:
            ticker_cond = df['ticker']==ticker
            bought_cond = df['bought']==1
            not_bought_cond = df['bought']==0

            df_ticker=df[ticker_cond]
            df_bought=df[ticker_cond & bought_cond]
            df_not_bought=df[ticker_cond & not_bought_cond]

            x_ticker=pd.to_datetime(df_ticker.timestamps)
            x_bought=pd.to_datetime(df_bought.timestamps)
            x_not_bought=pd.to_datetime(df_not_bought.timestamps)

            #x_ticks=df_ticker.set_index('timestamps').resample(pd.Timedelta('1 day')).first().reset_index().timestamps.to_list()

            ybid_bought=df_bought.bid
            yask_bought=df_bought.ask
            ybid_not_bought=df_not_bought.bid
            yEMA_small=df_ticker.EMA_small
            yEMA_big=df_ticker.EMA_big

            ax=plt.gca()
            plt.rcParams.update({'axes.titlesize': 20})
            plt.rcParams.update({'axes.titleweight': 'roman'})
            ax.xaxis_date()
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y/%m/%d-%H:%M:%S'))
            #plt.xticks(x_ticks,rotation=45)
            plt.xticks(rotation=45)
            plt.grid(True)

            plt.title("Stock data for {}".format(ticker),pad=18)
            plt.ylabel("Stock prices [USD]",labelpad=10)
            
            ax.scatter(x_bought,ybid_bought,c='tab:olive',marker='.',alpha=0.4,linewidths=0.8,label="Bids bought")
            ax.scatter(x_bought,yask_bought,c='tab:green',marker='.',alpha=0.4,linewidths=0.8,label="Asks bought")
            ax.scatter(x_not_bought,ybid_not_bought,c='tab:red',marker='.',alpha=0.4,linewidths=0.8,label="Bids not bought")
            ax.scatter(x_ticker,yEMA_small,c='tab:blue',marker='.',alpha=0.4,linewidths=0.8,label="Small EMA")
            ax.scatter(x_ticker,yEMA_big,c='tab:cyan',marker='.',alpha=0.4,linewidths=0.8,label="Big EMA")

            ax.legend()

            fig=plt.gcf()
            fig.set_size_inches(15,8)

            file_list=glob.glob(output_dir_plots+"/*{}*.png".format(ticker.upper()))
            for f in file_list:
                os.remove(f)

            plt.tight_layout()
            #plt.show()
            plt.savefig(output_dir_plots+"/{}_{}.png".format(utils.date_now_filename(),ticker),dpi=400)
            plt.clf()
            plt.cla()
            plt.close()







