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
from datetime import date, time, datetime, timedelta
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


def get_latest_prices(stock, data):
    # FUNCTION='get_latest_values'
    '''
    returns tuple: (timestamp_data,price_to_sell,price_to_buy,price_current_value)
    '''
    timestamp = datetime.strftime(data['timestamps'][-1], "%Y-%m-%d %H:%M:%S")
    price_to_buy = round(data['high'][-1], 2)
    price_to_sell = round(data['low'][-1], 2)
    price_current_value = round((data['open'][-1]+data['close'][-1])/2, 2)

    return (timestamp, price_to_sell, price_to_buy, price_current_value)


class AcceptParameters:
    def __init__(self, stock, exchange, df_data, config_params):
        self.stock = stock
        self.exchange = exchange
        self.df_data = df_data
        self.config_params = config_params

        self.EMA_surface_plus = "N/A"
        self.EMA_surface_min = "N/A"
        self.bigEMA_derivative = "N/A"
        self.surface_indicator = "N/A"
        self.number_of_EMA_crossings = "N/A"
        self.latest_drop = "N/A"
        self.support_level = "N/A"
        self.drop_period = config_params['trade_logic']['drop_period']

        self.df_data['timestamps'] = self.df_data['timestamps'].map(
            lambda timestamp: timestamp.replace(tzinfo=pytz.timezone("Etc/GMT-4")))

    def get_support_level(self):
        '''
        Calculates the support level for the stock in question.
        '''
        timestamps = self.df_data.timestamps
        data_sampling = timestamps.iloc[1]-timestamps.iloc[0]
        timedelta_period = timedelta(
            seconds=86400*self.config_params['trade_logic']['support_days'])
        data_points = round(timedelta_period/data_sampling)

        df_rel = self.df_data.tail(data_points)

        min_value = df_rel.close.min()
        perc = self.config_params['trade_logic']['support_percentage']/100

        return min_value*perc

    def accept_support_level(self):
        '''
        This function checks whether we should sell a stock because it drops below
        it's support level.
        '''
        support_level = self.get_support_level()
        latest_price = self.df_data.close.iloc[-1]

        return latest_price > support_level

    def is_overvalued(self):
        '''
        This function checks if, at the latest timestamp available, the stock is overvalued.
        '''
        latest_small_EMA = self.df_data.iloc[-1].smallEMA
        latest_big_EMA = self.df_data.iloc[-1].bigEMA

        return latest_small_EMA > latest_big_EMA

    def get_EMA_areas(self, ndays=2, logger=None):
        FUNCTION = 'get_EMA_areas'
        '''
        Calculate the area of the difference between small and 
        big EMA lines, for the last ndays days.
        '''
        start = utils.get_start_business_date(self.exchange, ndays+1, logger)

        if logger:
            logger.debug("Getting EMA areas starting from {}".format(
                start.strftime("%Y/%m/%d-%H:%M:%S")), extra={'function': FUNCTION})

        df_f = self.df_data[self.df_data['timestamps'] >= start]

        smallEMAs = df_f.smallEMA
        bigEMAs = df_f.bigEMA

        return utils.calculate_surfaces_EMAs(smallEMAs, bigEMAs, logger)

    def get_latest_drop(self, period, logger):
        FUNCTION='get_latest_drop'
        '''
        Gets the latest drop of the price of the stock, in %/h
        '''
        timestamps = self.df_data.timestamps
        data_sampling = timestamps.iloc[-1]-timestamps.iloc[-2]
        timedelta_period = timedelta(seconds=period)
        data_points = round(timedelta_period/data_sampling)

        df_rel = self.df_data.tail(data_points)

        if df_rel.empty:
            logger.info("Empty DataFrame was obtained with {} latest datapoints (data sampling: {} period: {})".format(data_points,data_sampling,period),extra={'function':FUNCTION})
            return False

        max_val = df_rel.close.max()
        min_val = df_rel.close.min()
        rel_diff_perc = (min_val-max_val)/(min_val+max_val)*2*100

        time_diff = df_rel.timestamps.loc[df_rel.close.idxmax()] - df_rel.timestamps.loc[df_rel.close.idxmin()]
        time_diff_seconds = abs(time_diff.total_seconds())
        factor = time_diff_seconds/3600

        return rel_diff_perc/factor

    def accept_latest_drop(self, logger):
        FUNCTION = 'accept_latest_drop'
        latest_drop = self.get_latest_drop(self.config_params['trade_logic']['drop_period'],logger=logger)
        if not latest_drop:
            logger.debug("Ticker: {}. Latest drop could not be calculated".format(self.stock),extra={'function':FUNCTION})
            return False
        if latest_drop < self.config_params['trade_logic']['drop_threshold']:
            logger.debug("Ticker: {}. Latest drop ({}%/h) is greater than the configured threshold ({}%/h)".format(
                self.stock, latest_drop, self.config_params['trade_logic']['drop_threshold']), extra={'function': FUNCTION})
            return False

        return True

    def get_number_EMA_crossings(self, ndays=2, logger=None):
        FUNCTION = 'get_number_EMA_crossings'
        '''
        Calculate the number of times the bigEMA line crosses the smallEMA line.
        '''
        start = utils.get_start_business_date(self.exchange, ndays+1, logger)

        if logger:
            logger.debug("Getting number of EMA crossings starting from {}".format(
                start.strftime("%Y/%m/%d-%H:%M:%S")), extra={'function': FUNCTION})

        df_f = self.df_data[self.df_data['timestamps'] >= start]

        smallEMAs = df_f.smallEMA
        bigEMAs = df_f.bigEMA

        return utils.get_number_of_crossings(smallEMAs, bigEMAs, logger)

    def accept_stock(self, logger):
        FUNCTION = 'accept_stock'
        '''
        Check whether we should monitor de stock or not.
        '''
        logger.debug("Checking whether we want to accept stock {} or not".format(
            self.stock), extra={'function': FUNCTION})
        result = True
        bigEMAs = self.df_data.bigEMA

        if len(bigEMAs) < self.config_params['trade_logic']['number_of_big_EMAs_threshold']:
            result = False
            logger.debug("Ticker: {}. There weren't enough bigEMA measurements ({} vs required {}) to make a decision".format(
                self.stock, len(bigEMAs), self.config_params['trade_logic']['number_of_big_EMAs_threshold']), extra={'function': FUNCTION})

        D, A = utils.get_deriv_surf(bigEMAs, logger)
        self.bigEMA_derivative = D
        self.surface_indicator = A

        if abs(D) > self.config_params['trade_logic']['big_EMA_derivative_threshold']:
            result = False
            logger.debug("Ticker: {}. Derivative is too steep ({} vs required {})".format(self.stock, abs(
                D), self.config_params['trade_logic']['big_EMA_derivative_threshold']), extra={'function': FUNCTION})

        if A > self.config_params['trade_logic']['surface_indicator_threshold']:
            result = False
            logger.debug("Ticker: {}. Surface indicator is too high ({} vs required {})".format(
                self.stock, A, self.config_params['trade_logic']['surface_indicator_threshold']), extra={'function': FUNCTION})

        areas = self.get_EMA_areas(logger=logger)
        if not areas:
            logger.debug("Ticker: {}. Impossible to calculate EMA areas.".format(
                self.stock), extra={'function': FUNCTION})
            return False

        self.EMA_surface_plus = round(areas[0], 3)
        self.EMA_surface_min = round(areas[1], 3)

        if self.config_params['trade_logic']['EMA_surface_plus_threshold'] < self.EMA_surface_plus:
            logger.debug("Ticker: {}. EMA surface plus ({}) if higher than the threshold ({})".format(
                self.stock, self.EMA_surface_plus, self.config_params['trade_logic']['EMA_surface_plus_threshold']), extra={'function': FUNCTION})
            result = False

        if self.config_params['trade_logic']['EMA_surface_min_threshold'] > self.EMA_surface_min:
            logger.debug("Ticker: {}. EMA surface min ({}) if lower than the threshold ({})".format(
                self.stock, self.EMA_surface_min, self.config_params['trade_logic']['EMA_surface_min_threshold']), extra={'function': FUNCTION})
            result = False

        number_of_crossings = self.get_number_EMA_crossings(logger=logger)

        if number_of_crossings == None:
            logger.debug("Ticker: {}. Impossible to calculate number of EMA crossings.".format(
                self.stock), extra={'function': FUNCTION})
            return False

        self.number_of_EMA_crossings = number_of_crossings

        if self.number_of_EMA_crossings < self.config_params['trade_logic']['number_of_EMA_crossings']:
            logger.debug("Ticker: {}. Number of EMA crossings ({}) is smaller than threshold ({})".format(
                self.stock, self.number_of_EMA_crossings, self.config_params['trade_logic']['number_of_EMA_crossings']), extra={'function': FUNCTION})
            result = False

        if not self.is_overvalued():
            logger.debug("Ticker {}. Not overvalued, not accepted.".format(
                self.stock), extra={'function': FUNCTION})

        '''
        latest_drop = self.get_latest_drop(self.config_params['trade_logic']['drop_period'])
        self.latest_drop = latest_drop

        if self.latest_drop<self.config_params['trade_logic']['drop_threshold']:
            logger.debug("Ticker: {}. Latest drop ({}%/h) is greater than the configured threshold ({}%/h)".format(self.stock,self.latest_drop,self.config_params['trade_logic']['drop_threshold']),extra={'function':FUNCTION})
            result=False
        '''

        return result


class Stocks:
    def __init__(self,
                 balance=[0, 0],
                 bought_stocks={},
                 monitored_stocks=[],
                 monitored_stock_data={},
                 archive=[],
                 current_status={},
                 interesting_stocks=[],
                 not_interesting_stocks=[],
                 yahoo_calls={},
                 results={}):
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
                "timestamp_bought" : ""
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
                    'fullname' : ...,
                    'timestamp_bought' : ...,
                    'timestamp_sold' : ...,
                    'net_profit_loss' : ...,
                    'derivative_factor' : ...,
                    'surface_factor' : ...,
                    'EMA_surface_plus' : ...,
                    'EMA_surface_min' : ...,
                    'number_of_EMA_crossings' : ...
                },
                ...
            ]
        interesting_stocks : []
        not_interesting_stocks : []
        yahoo_calls : 
            {
                'day_timestamp' : datetime.date,
                'hour_timestamp' : datetime.datetime,
                'daily_calls' : ...,
                'hourly_calls' : ...
            }
        '''
        self.balance = balance
        self.bought_stocks = bought_stocks
        self.monitored_stocks = monitored_stocks
        self.monitored_stock_data = monitored_stock_data
        self.archive = archive
        self.current_status = current_status
        self.interesting_stocks = interesting_stocks
        self.not_interesting_stocks = not_interesting_stocks
        self.yahoo_calls = yahoo_calls

        self.initial_virtual_result = 0
        self.initial_final_result = 0

        for key in self.current_status:
            if self.current_status[key]['virtual_result'] != "-":
                self.initial_virtual_result += float(
                    self.current_status[key]['virtual_result'])

        for transaction in self.archive:
            self.initial_final_result += float(transaction['net_profit_loss'])

        if not results:
            self.results = {utils.date_now_flutter():{
                "virtual_result":self.initial_virtual_result,
                "final_result":self.initial_final_result
            }}
        else:
            self.results=results
            self.results[utils.date_now_flutter()]={
                "virtual_result":self.initial_virtual_result,
                "final_result":self.initial_final_result
            }

    def update_yahoo_calls(self, add_call, logger):
        FUNCTION = 'add_yahoo_call'
        '''
        Add yahoo call to the records. This is done in order to check compliance with the limits.
        '''
        if not self.yahoo_calls:
            self.yahoo_calls = {
                'last_timestamp_day': utils.date_now(),
                'last_hour': datetime.now().hour,
                'daily_calls': 0,
                'hourly_calls': 0
            }

        data = self.yahoo_calls
        last_date = datetime.strptime(
            data['last_timestamp_day'], "%Y/%m/%d-%H:%M:%S").date()
        now = datetime.now()

        if now.date() > last_date:
            data['last_timestamp_day'] = utils.date_now()
            data['daily_calls'] = 1
        elif now.date() == last_date:
            if add_call:
                data['daily_calls'] += 1
        else:
            logger.error("Day present in object is after current day. Bad bad programmer, this should never occur.", extra={
                         'function': FUNCTION})

        if now.hour > data['last_hour'] or now.hour < data['last_hour']:
            data['last_hour'] = now.hour
            data['hourly_calls'] = 1
        elif now.hour == data['last_hour']:
            if add_call:
                data['hourly_calls'] += 1

    def get_latest_data(self, ticker, exchange, config_params, logger):
        # FUNCTION='get_latest_data'
        '''
        Description
        '''
        yah = YahooAPI()

        start_day = utils.get_start_business_date(
            exchange, config_params['trade_logic']['yahoo_period_historic_data'], logger)
        if not start_day:
            return pd.DataFrame

        days_in_past = (datetime.now(pytz.timezone('UTC'))-start_day).days+1

        start = datetime.strftime(
            datetime.now()-timedelta(days=days_in_past), '%Y/%m/%d-%H:%M:%S')
        end = datetime.strftime(datetime.now(), '%Y/%m/%d-%H:%M:%S')

        df_data = yah.get_data(ticker, start, end, config_params['trade_logic']['yahoo_interval'], config_params['trade_logic']
                               ['yahoo_period_small_EMA'], config_params['trade_logic']['yahoo_period_big_EMA'], logger=logger)

        self.update_yahoo_calls(add_call=True, logger=logger)

        return df_data

    def get_new_interesting_stock(self, logger):
        FUNCTION = 'get_new_interesting_stock'
        '''
        Return a new interesting stock which is currently not monitored and excludiding any manually 
        passed stocks.
        '''
        result = ""
        for stock in self.interesting_stocks:
            if stock in self.not_interesting_stocks:
                continue
            if stock in self.monitored_stocks:
                continue
            result = stock

        if not result:
            logger.error("No new interesting stock was found :(",
                         extra={'function': FUNCTION})

        return result

    def accept_new_stock(self, stock, df_data, config_params, logger):
        FUNCTION = 'accept_new_stock'
        '''
        Check if we will monitor the given stock.
        '''
        big_EMAs = df_data.bigEMA

        if len(big_EMAs) < config_params['trade_logic']['number_of_big_EMAs_threshold']:
            logger.debug("Ticker: {}. There weren't enough bigEMA measurements ({} vs required {}) to make a decision".format(
                stock, len(big_EMAs), config_params['trade_logic']['number_of_big_EMAs_threshold']), extra={'function': FUNCTION})
            self.not_interesting_stocks.append(stock)
            return False, 0, 0

        D, A = utils.get_deriv_surf(big_EMAs, logger)
        logger.debug("Ticker: {}. Derivative: {} and surface indicator: {}.".format(
            stock, D, A), extra={'function': FUNCTION})

        if abs(D) > config_params['trade_logic']['big_EMA_derivative_threshold']:
            logger.debug("Ticker: {}. Derivative is too steep ({} vs required {})".format(stock, abs(
                D), config_params['trade_logic']['big_EMA_derivative_threshold']), extra={'function': FUNCTION})
            self.not_interesting_stocks.append(stock)
            return False, 0, 0

        if A > config_params['trade_logic']['surface_indicator_threshold']:
            logger.debug("Ticker: {}. Surface indicator is too high ({} vs required {})".format(
                stock, A, config_params['trade_logic']['surface_indicator_threshold']), extra={'function': FUNCTION})
            self.not_interesting_stocks.append(stock)
            return False, 0, 0

        return True, D, A

    def add_new_stock(self, stock, df_data, exchange, params, fullname, description, market_state, logger):
        FUNCTION = 'add_new_stock'
        '''
        Add new stock
        '''
        if not stock in self.monitored_stocks:
            self.monitored_stocks.append(stock)

        self.monitored_stock_data[stock] = df_data.to_dict(orient='list')

        if stock in self.current_status:
            data = df_data.to_dict(orient='list')
            latest_prices = get_latest_prices(stock, data)
            timestamp_data = latest_prices[0]
            # price_to_sell=latest_prices[1]
            # price_to_buy=latest_prices[2]
            price_current_value = latest_prices[3]
            number = self.current_status[stock]["number"]
            if number == "-":
                current_value = "-"
            else:
                current_value = round(price_current_value*number, 2)

            value_bought = self.current_status[stock]["value_bought"]
            if value_bought == "-" or number == "-":
                virtual_result = "-"
            else:
                virtual_result = round(
                    price_current_value*number-value_bought, 2)

            self.current_status[stock]["timestamp_updated"] = utils.date_now_flutter(
            )
            self.current_status[stock]["timestamp_data"] = timestamp_data
            self.current_status[stock]["value_current"] = current_value
            self.current_status[stock]["virtual_result"] = virtual_result
            self.current_status[stock]["market_status"] = market_state
        else:
            self.current_status[stock] = {"fullname": fullname,
                                          "number": "-",
                                          "bought": "NO",
                                          "value_bought": "-",
                                          "value_current": "-",
                                          "virtual_result": "-",
                                          "timestamp_bought": "-",
                                          "market_state": market_state,
                                          "timestamp_updated": utils.date_now_flutter(),
                                          "timestamp_data": "-",
                                          "description": description,
                                          "exchange": exchange,
                                          "derivative_factor": round(params.bigEMA_derivative, 8),
                                          "surface_factor": round(params.surface_indicator, 8),
                                          "EMA_surface_plus": round(params.EMA_surface_plus, 8),
                                          "EMA_surface_min": round(params.EMA_surface_min, 8),
                                          "number_of_EMA_crossings": params.number_of_EMA_crossings,
                                          "drop_period": params.drop_period,
                                          "latest_drop": params.latest_drop,
                                          "support_level": params.support_level
                                          }

        logger.info("Stock {} was added to the list of stocks to be monitored".format(
            stock), extra={'function': FUNCTION})

    def check_to_monitor_new_stocks(self, config_params, logger):
        FUNCTION = 'check_to_monitor_new_stocks'
        '''
        Check if we should add a new stock to monitor
        '''
        while len(self.monitored_stocks) < config_params['main']['initial_number_of_stocks']:
            ticker = self.get_new_interesting_stock(logger)

            logger.debug("Checking {}".format(ticker),
                         extra={'function': FUNCTION})
            scraper = YahooScraper()
            exchange = scraper.get_exchange(ticker, logger)
            if not exchange:
                self.not_interesting_stocks.append(ticker)
                logger.debug("Ticker {} was skipped because no valid response was received from the get_exchange function.".format(
                    ticker), extra={'function': FUNCTION})
                continue

            df_data = self.get_latest_data(
                ticker, exchange, config_params, logger)

            if df_data.empty:
                self.not_interesting_stocks.append(ticker)
                logger.debug("No data was received from the yahooAPI", extra={
                             'function': FUNCTION})
                continue

            params = AcceptParameters(ticker, exchange, df_data, config_params)

            if not params.accept_stock(logger):
                self.not_interesting_stocks.append(ticker)
                logger.debug("Ticker {} was skipped because it didn't pass the tests.".format(
                    ticker), extra={'function': FUNCTION})
                continue

            fullname = scraper.get_fullname(ticker, logger)
            if not fullname:
                self.not_interesting_stocks.append(ticker)
                logger.debug("Ticker {} was skipped because no valid response was received from the get_fullname function.".format(
                    ticker), extra={'function': FUNCTION})
                continue

            description = scraper.get_description(ticker, logger)
            if not description:
                self.not_interesting_stocks.append(ticker)
                logger.debug("Ticker {} was skipped because no valid response was received from the get_description function.".format(
                    ticker), extra={'function': FUNCTION})
                continue

            market_state = scraper.check_market_state(ticker, logger=logger)
            if market_state == "UNKNOWN":
                self.not_interesting_stocks.append(ticker)
                logger.debug("Ticker {} was skipped because no valid response was received from the check_market_state function.".format(
                    ticker), extra={'function': FUNCTION})
                continue

            self.add_new_stock(ticker, df_data, exchange, params,
                               fullname, description, market_state, logger)

    def initialize_stocks(self, logger, config_params, update_nasdaq_file=False):
        FUNCTION = 'initialize_stocks'
        '''
        1) find interesting stocks
        2) initialize data for found list in 1)
        '''
        logger.debug("Getting stocks to monitor", extra={'function': FUNCTION})

        # TODO this is only for NASDAQ!
        file = './nasdaqtraded.txt'
        if update_nasdaq_file:
            logger.info("Updating nasdaqtraded file",
                        extra={'function': FUNCTION})
            with closing(request.urlopen('ftp://ftp.nasdaqtrader.com/symboldirectory/nasdaqtraded.txt')) as r:
                with open(file, 'wb') as f:
                    shutil.copyfileobj(r, f)

        df = pd.read_csv(file, delimiter='|')
        df.drop(df.tail(1).index, inplace=True)

        self.interesting_stocks = list(set(df.Symbol))

        self.check_to_monitor_new_stocks(config_params, logger)

        logger.debug("Initialized stocks", extra={'function': FUNCTION})
        return True

    def buy_stock(self, stock, money_to_spend, price_to_buy, timestamp_data, logger):
        FUNCTION = 'buy_stock'

        # TODO check if market is open

        number_to_buy = round(money_to_spend/price_to_buy, 2)
        money_spent = round(number_to_buy*price_to_buy, 2)

        self.bought_stocks[stock] = (number_to_buy, money_spent)

        self.current_status[stock]["number"] = number_to_buy
        self.current_status[stock]["bought"] = "YES"
        self.current_status[stock]["value_bought"] = money_spent
        self.current_status[stock]["value_current"] = money_spent
        self.current_status[stock]["virtual_result"] = 0
        self.current_status[stock]["timestamp_bought"] = utils.date_now_flutter()
        self.current_status[stock]["timestamp_data"] = timestamp_data
        self.current_status[stock]["timestamp_updated"] = utils.date_now_flutter()

        self.balance[1] -= money_spent

        logger.info("${} worth of {} stocks were bought.".format(
            money_spent, stock), extra={'function': FUNCTION})

    def check_yahoo_latency(self, stock, timestamp, threshold, logger):
        FUNCTION = 'check_yahoo_latency'

        latest_timestamp = datetime(1970, 1, 1)
        if isinstance(timestamp, str):
            latest_timestamp = datetime.strptime(
                timestamp, '%Y/%m/%d-%H:%M:%S')
        else:
            latest_timestamp = timestamp

        print("GLENNY now: ",datetime.now())
        print("GLENNY latest: ",latest_timestamp)
        latency = datetime.now()-latest_timestamp
        if latency.total_seconds()-6*3600 > threshold:
            # latest data from yahoo is not valid anymore
            logger.info("Stock {} was not bought because only outdated information from the yahooAPI was received. Latency of {}s is considered with a threshold of {}s".format(
                stock, latency.total_seconds()-6*3600, threshold), extra={'function': FUNCTION})
            return False

        logger.debug("Ticker: {}. Latency check ok, obtained {}s for a threshold of {}s".format(
            stock, latency.total_seconds()-6*3600, threshold), extra={'function': FUNCTION})

        return True

    def sell_stock(self, stock, price_to_sell, timestamp_data, reason, logger):
        FUNCTION = 'sell_stock'

        if not stock in self.bought_stocks:
            logger.debug("Trying to sell stocks from {}, but no stocks from this company are owned ATM.".format(
                stock), extra={'function': FUNCTION})
            return False

        value_bought = self.current_status[stock]["value_bought"]
        current_value = round(self.bought_stocks[stock][0]*price_to_sell, 2)
        scraper = YahooScraper()

        new_archive = {
            'ticker': stock,
            'fullname': scraper.get_fullname(stock, logger),
            'timestamp_bought': self.current_status[stock]["timestamp_bought"],
            'timestamp_sold': utils.date_now_flutter(),
            'net_profit_loss': current_value-value_bought,
            'reason': reason,
            'derivative_factor': self.current_status[stock]['derivative_factor'],
            'surface_factor': self.current_status[stock]['surface_factor'],
            'EMA_surface_plus': self.current_status[stock]['EMA_surface_plus'],
            'EMA_surface_min': self.current_status[stock]['EMA_surface_min'],
            'number_of_EMA_crossings': self.current_status[stock]['number_of_EMA_crossings'],
        }

        self.bought_stocks.pop(stock)
        self.current_status.pop(stock)
        self.monitored_stock_data.pop(stock)
        self.monitored_stocks.remove(stock)

        self.archive.append(new_archive)

        self.balance[1] += current_value

        self.not_interesting_stocks.append(stock)

        logger.info("All stocks of {} were sold for a total of ${}".format(
            stock, current_value), extra={'function': FUNCTION})

        return True

    def check_monitored_stock(self, stock, config_params, logger):
        FUNCTION = 'check_monitored_stock'
        '''
        This function checks in on a stock that is being monitored.
        '''
        scraper = YahooScraper()
        stock_bought = (stock in self.bought_stocks)
        market_state = scraper.check_market_state(stock, logger=logger)
        self.current_status[stock]["market_state"] = market_state
        exchange = self.current_status[stock]["exchange"]

        df_data = self.get_latest_data(stock, exchange, config_params, logger)
        if df_data.empty:
            return False

        data = df_data.to_dict(orient='list')
        latest_prices = get_latest_prices(stock, data)
        timestamp_data = latest_prices[0]
        price_to_sell = latest_prices[1]
        price_to_buy = latest_prices[2]
        price_current_value = latest_prices[3]

        smallEMAs = data['smallEMA']
        bigEMAs = data['bigEMA']

        undervalued = (smallEMAs[-1] < bigEMAs[-1])

        # TODO update current status better (virtual result)
        if market_state == "CLOSED" and not config_params['main']['ignore_market_hours']:
            logger.info("No checks were performed because the market for {} is closed.".format(
                stock), extra={'function': FUNCTION})
            return True

        if stock_bought and undervalued:
            # UPDATE AND PASS
            logger.debug("Stock {} is bought and undervalued => update and pass.".format(
                stock), extra={'function': FUNCTION})
            number_stocks_owned = self.bought_stocks[stock][0]
            value_bought = self.current_status[stock]["value_bought"]

            self.current_status[stock]["value_current"] = round(
                price_current_value*number_stocks_owned, 2)
            self.current_status[stock]["virtual_result"] = round(
                price_current_value*number_stocks_owned-value_bought, 2)
            self.current_status[stock]["timestamp_data"] = timestamp_data
            self.current_status[stock]["timestamp_updated"] = utils.date_now_flutter(
            )

            self.monitored_stock_data[stock] = df_data.to_dict(orient='list')

            accept = AcceptParameters(stock, exchange, df_data, config_params)
            self.current_status[stock]["support_level"]=accept.support_level
            if not accept.accept_support_level():
                logger.info("Stock {} is sold because it has dropped below it's support level.".format(
                    stock), extra={'function': FUNCTION})
                reason = "Support level."
                self.sell_stock(stock, price_to_sell,
                                timestamp_data, reason, logger)

        elif (not stock_bought) and (not undervalued):
            # PASS
            logger.debug("Stock {} is not bought and overvalued => pass.".format(
                stock), extra={'function': FUNCTION})
            pass
        elif (not stock_bought) and undervalued:
            # BUY
            logger.info("Stock {} is not bought and undervalued => buy.".format(
                stock), extra={'function': FUNCTION})
            mytime = data['timestamps'][-1]

            latency_check = self.check_yahoo_latency(
                stock, mytime, config_params['trade_logic']['yahoo_latency_threshold'], logger)
            if not latency_check:
                logger.info("Stock {} was not bought because it didn't pass the latency check.", extra={
                            'function': FUNCTION})
                return

            accept = AcceptParameters(stock, exchange, df_data, config_params)
            self.current_status[stock]["latest_drop"]=accept.latest_drop
            if not accept.accept_latest_drop(logger=logger):
                logger.info("Stock {} was not bought because it didn't pass the latest drop check.".format(
                    stock), extra={'function': FUNCTION})
                return

            self.buy_stock(
                stock, config_params['trade_logic']['money_to_spend'], price_to_buy, timestamp_data, logger)

        elif stock_bought and (not undervalued):
            # SELL
            logger.info("Stock {} is bought and overvalued => sell.".format(
                stock), extra={'function': FUNCTION})
            mytime = data['timestamps'][-1]

            latency_check = self.check_yahoo_latency(
                stock, mytime, config_params['trade_logic']['yahoo_latency_threshold'], logger)
            if latency_check:
                reason = "Overvalued again."
                self.sell_stock(stock, price_to_sell,
                                timestamp_data, reason, logger)
            else:
                logger.info("Stock {} is not sold because it did't pass the latency check.", extra={
                            'function': FUNCTION})

        # This next option should never occur.
        else:
            logger.error("Strange combination", extra={'function': FUNCTION})

    def hard_sell_check(self, commands, command_log, config_params, logger):
        FUNCTION = 'hard_sell_check'
        '''
        This function checks whether the user has ordered to sell certain stocks using the app,
        and sells them.
        '''
        tickers = commands['tickers_to_sell']
        remove_all_stocks = False
        to_remove = []
        if "ALLSTOCKS" in tickers:
            remove_all_stocks = True
            tickers = list(self.bought_stocks.keys())
            to_remove.append("ALLSTOCKS")
            if "commands" in commands and "SELLALL" in commands["commands"]:
                commands["commands"].remove("SELLALL")

        if not tickers:
            return True

        
        for ticker in tickers:
            logger.debug("Trying to sell {} stocks".format(
                ticker), extra={'function': FUNCTION})
            if not ticker in self.current_status or self.current_status[ticker]["bought"] == "NO":
                logger.debug("Trying to sell stocks from {}, but no stocks from this company are owned ATM.".format(
                    ticker), extra={'function': FUNCTION})
                to_remove.append(ticker)
                continue

            exchange = self.current_status[ticker]["exchange"]

            df_data = self.get_latest_data(
                ticker, exchange, config_params, logger)
            if df_data.empty:
                logger.debug("Ticker {}. Unable to obtain latest data, ticker is not sold.".format(
                    ticker), extra={'function': FUNCTION})
                continue

            data = df_data.to_dict(orient='list')
            latest_prices = get_latest_prices(ticker, data)
            timestamp_data = latest_prices[0]
            price_to_sell = latest_prices[1]
            # price_to_buy=latest_prices[2]
            # price_current_value=latest_prices[3]

            data = self.monitored_stock_data[ticker]
            price_to_sell = round(data['low'][-1], 2)
            reason = "Forced by user."

            success = self.sell_stock(
                ticker, price_to_sell, timestamp_data, reason, logger)
            if success:
                to_remove.append(ticker)

        if remove_all_stocks:
            commands['tickers_to_sell'] = []
        else:
            for ticker in to_remove:
                commands['tickers_to_sell'].remove(ticker)

        utils.write_json(commands, command_log, logger=logger)

    def stop_monitor(self, stock):
        '''
        Stop monitoring the provided stock.
        '''
        if stock in self.monitored_stocks:
            self.monitored_stocks.remove(stock)

        if stock in self.monitored_stock_data.keys():
            self.monitored_stock_data.pop(stock)

        self.not_interesting_stocks.append(stock)

    def check_to_stop_monitor_stocks(self, commands, command_log, config_params, logger):
        FUNCTION = 'hardcheck_to_stop_monitor_stocks_buy_check'
        '''
        This function checks whether the user has ordered to stop monitor certain stocks 
        using the app.
        '''
        tickers = commands['tickers_to_stop_monitor']

        if not tickers:
            return True

        to_remove = []
        for ticker in tickers:
            if not ticker in self.monitored_stocks or self.current_status[ticker]["bought"] == "YES":
                logger.debug("Trying to stop monitor stocks from {}, but no stocks from this company are monitored atm or they are already bought.".format(
                    ticker), extra={'function': FUNCTION})
                to_remove.append(ticker)
                continue

            self.stop_monitor(ticker)
            to_remove.append(ticker)

        for ticker in to_remove:
            commands['tickers_to_stop_monitor'].remove(ticker)

        utils.write_json(commands, command_log, logger=logger)

    def plot_monitored_stock_data(self, output_dir_plots, logger):
        FUNCTION = 'plot_monitored_stock_data'
        '''
        This function plots the evolution of the prices per stock.
        '''

        data = self.monitored_stock_data
        for ticker in data:
            df = pd.DataFrame(data[ticker])

            timestamps = pd.to_datetime(df.timestamps)
            delta = timedelta(minutes=1)
            for i in range(len(timestamps)-1):
                if timestamps.iloc[i].date() == timestamps.iloc[i+1].date():
                    delta = timestamps.iloc[i+1]-timestamps.iloc[i]
                    break

            df = df.resample(delta, on='timestamps').last().fillna(np.nan)
            df = df.drop(columns='timestamps').reset_index()

            if df.empty:
                logger.debug("No valid data for monitored stock {}".format(
                    ticker), extra={'function': FUNCTION})
                continue

            x_dates = pd.to_datetime(df.timestamps)

            y_close = df.close
            y_smallEMA = df.smallEMA
            y_bigEMA = df.bigEMA

            ax = plt.gca()
            plt.rcParams.update({'axes.titlesize': 20})
            plt.rcParams.update({'axes.titleweight': 'roman'})
            ax.xaxis_date()
            ax.xaxis.set_major_formatter(
                mdates.DateFormatter('%Y/%m/%d-%H:%M:%S'))

            plt.xticks(rotation=45)
            plt.grid(True)

            plt.title("Stock data for {}".format(ticker), pad=18)
            plt.ylabel("Stock prices [USD]", labelpad=10)

            ax.plot(x_dates, y_close, c='tab:blue', marker=',',
                    alpha=1, linewidth=1.2, label="Closes")
            ax.plot(x_dates, y_smallEMA, c='tab:cyan', marker=',',
                    alpha=1, linewidth=1.2, label="smallEMA")
            ax.plot(x_dates, y_bigEMA, c='tab:purple', marker=',',
                    alpha=1, linewidth=1.2, label="bigEMA")

            ax.legend()

            fig = plt.gcf()
            fig.set_size_inches(15, 8)

            file_list = glob.glob(
                output_dir_plots+"/*{}*.png".format(ticker.upper()))
            for f in file_list:
                os.remove(f)

            plt.tight_layout()
            plt.savefig(
                output_dir_plots+"/{}_{}.png".format(utils.date_now_filename(), ticker), dpi=400)
            plt.clf()
            plt.cla()
            plt.close()

    def get_overview(self, logger, algo_running="Yes"):
        # FUNCTION='get_overview'
        '''
        This function gets the total overview of the current status, in the following form:
        {timestamp: {   'total_virtual_result':...,
                        'total_final_result':...,
                        'number_of_stocks_owned':...
                    }
        }
        '''
        total_final_result = 0
        total_virtual_result = 0
        total_value_current = 0
        number_of_stocks_monitored = 0
        number_of_stocks_owned = 0
        data = self.current_status

        for key in data:
            number_of_stocks_monitored += 1
            if data[key]["bought"] == "YES":
                number_of_stocks_owned += 1
                total_value_current += data[key]["value_current"]

            if data[key]['virtual_result'] != "-":
                total_virtual_result += float(data[key]['virtual_result'])

        for archive in self.archive:
            total_final_result += archive["net_profit_loss"]

        result = {
            'starting_balance': self.balance[0],
            'initial_virtual_result': self.initial_virtual_result,
            'initial_final_result': self.initial_final_result,
            'balance': self.balance[1],
            'total_value_current': total_value_current,
            'algorithm_running': algo_running,
            'timestamp': utils.date_now_flutter(),
            'total_virtual_result': round(total_virtual_result, 2),
            'total_final_result': round(total_final_result, 2),
            'number_of_stocks_owned': number_of_stocks_owned,
            'number_of_stocks_monitored': number_of_stocks_monitored,
            'yahoo_daily_calls': self.yahoo_calls['daily_calls'],
            'yahoo_hourly_calls': self.yahoo_calls['hourly_calls']
        }

        self.results[utils.date_now_flutter()]={
            "virtual_result":total_virtual_result,
            "final_result":total_final_result}

        return result
