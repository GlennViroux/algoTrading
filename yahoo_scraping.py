#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import pandas_market_calendars as mcal
from datetime import datetime,timedelta,timezone
import pandas as pd
from bs4 import BeautifulSoup as Soup
import re
import utils

MARKET_IDS={'NasdaqGS':'NASDAQ',
            'NasdaqCM':'NASDAQ',
            'NasdaqGM':'NASDAQ',
            'NYSE':'NYSE',
            'OtherOTC':'NASDAQ',
            'NYSEArca':'NYSE',
            'NYSEAmerican':'NYSE'}

class YahooScraper:
    def __init__(self):
        self.base_url="https://finance.yahoo.com/"

    def get_fullname(self,ticker,logger):
        FUNCTION='get_fullname'
        ticker_upper=ticker.upper()
        url=self.base_url+"quote/{}".format(ticker_upper)
        try:
            req=requests.get(url)
        except:
            logger.debug("Ticker: {}. Error while calling http get request from the yahoo website ({}).".format(ticker,url),extra={'function':FUNCTION})
            return None

        if not req.status_code==200:
            logger.debug("Ticker: {}. No valid resonse was obtained from the yahoo website. Status code: {}".format(ticker,req.status_code),extra={'function':FUNCTION})
            return None

        soep=Soup(req.text,'html.parser')
        text=soep.find(text=re.compile('.*({})'.format(ticker_upper)))
        fullname=text.split("({})".format(ticker_upper))[0]

        return fullname

    def get_exchange(self,ticker,logger):
        FUNCTION='get_exchange'
        '''
        Get the exchange on which the given ticker is traded.
        '''
        url=self.base_url+"quote/{}".format(ticker.upper())
        try:
            req=requests.get(url)
        except:
            logger.debug("Ticker: {}. Error while calling http get request from the yahoo website ({}).".format(ticker,url),extra={'function':FUNCTION})
            return None

        if not req.status_code==200:
            logger.debug("Ticker: {}. No valid resonse was obtained from the yahoo website. Status code: {}.".format(ticker,req.status_code),extra={'function':FUNCTION})
            return None

        soep=Soup(req.text,'html.parser')
        string=soep.find(text=re.compile('.*Currency in.*'))
        words=string.replace(".","").split("-")
        words=[word.replace(" ","") for word in words]

        if not len(words)==2:
            logger.debug("Length of market information from yahoo website is not two.",extra={'function':FUNCTION})
            return None

        result=""
        try:
            result=MARKET_IDS[words[0]]
        except KeyError:
            result=words[0]
             
        return result

    def check_market_state(self,ticker,logger):
        FUNCTION='check_market_state'
        '''
        Returns true if market for the provided ticker is open at this moment.
        '''
        url=self.base_url+"quote/{}".format(ticker.upper())
        result="UNKNOWN"
        try:
            req=requests.get(url)
        except:
            logger.debug("Ticker: {}. Error while calling http get request from the yahoo website ({}).".format(ticker,url),extra={'function':FUNCTION})
            return result

        if not req.status_code==200:
            logger.debug("Ticker: {}. No valid resonse was obtained from the yahoo website. \n\nUrl: {} \n\nStatus code: {}.".format(ticker,req.url,req.status_code),extra={'function':FUNCTION})
            return result

        soep=Soup(req.text,'html.parser')
        market_open=soep.find("span",text=re.compile('.*Market open.*'))
        market_closed=soep.find("span",text=re.compile('.*At close.*'))
        before_hours=soep.find("span",text=re.compile('.*Before hours.*'))
        after_hours=soep.find("span",text=re.compile('.*After hours.*'))

        if market_open:
            result="OPEN"
        elif market_closed and before_hours:
            result="BEFORE_HOURS"
        elif market_closed and after_hours:
            result="AFTER_HOURS"
        elif market_closed and not market_open and not before_hours and not after_hours:
            result="CLOSED"
        else:
            logger.warning("No valid combination: market_open {}, market_closed {}, before_hours {}, after_hours {}".format(market_open,market_closed,before_hours,after_hours),extra={'function':FUNCTION})

        return result

    def all_markets_closed(self,all_stocks,logger):
        #FUNCTION='all_markets_closed'
        '''
        This function returns True if all relevant stock markets are closed at this moment.
        '''
        for stock in all_stocks:
            state=self.check_market_state(stock,logger)
            if not state=="CLOSED":
                return False

        return True

    def get_description(self,ticker,logger):
        FUNCTION='get_description'
        '''
        This function returns the detailed description of the company.
        '''
        description=""
        url=self.base_url+"/quote/{}/profile".format(ticker)
        try:
            req=requests.get(url)
        except:
            logger.debug("Ticker: {}. No valid response was returned from the yahooAPI with url ({})".format(ticker,url),extra={'function':FUNCTION},exc_info=False)
            return description

        if not req.status_code==200:
            logger.debug("Ticker: {}. No valid response was returned from the yahooAPI. Status code: {}.".format(ticker,req.status_code),extra={'function':FUNCTION})
            return description

        soep=Soup(req.text,'html.parser')
        des_tag=soep.find(text="Description")

        try:
            description=des_tag.parent.parent.next_sibling.get_text()
        except:
            logger.debug("Ticker: {}. Error in get_text function".format(ticker),extra={'function':FUNCTION},exc_info=False)
            return description

        return description


'''
    def all_markets_closed(self,bought_stocks,logger):
        FUNCTION='all_markets_closed'
        This function returns True if all relevant stock markets are closed at this moment.
        for ticker in bought_stocks.keys():
            if self.check_market_state(ticker,logger)!="CLOSED":
                return False

        main_markets=["NASDAQ","NYSE"]
        for market in main_markets:
            cal=mcal.get_calendar(market)
            dt_now=datetime.now()
            schema = cal.schedule(start_date=datetime.strftime(dt_now-timedelta(days=1),'%Y-%m-%d'),end_date=datetime.strftime(dt_now+timedelta(days=1),'%Y-%m-%d'))

            if (cal.open_at_time(schema, datetime.now(tz=timezone.utc))):
                logger.debug("Exchange {} is open.".format(market),extra={'function':FUNCTION})
                return False

        logger.debug("Markets {} and {} are closed.".format(main_markets[0],main_markets[1]),extra={'function':FUNCTION})
        return True

    def get_bid_and_ask(self,ticker):
        
        return {'bid':bid_price,'bid_volume'=bid_volume,'ask'=ask_price,'ask_volume'=ask_volume}
        
        url=self.base_url+"quote/{}".format(ticker.upper())
        try:
            req=requests.get(url)
        except:
            return None

        if not req.status_code==200:
            print("Wrong status code.")
            print(req.status_code)
            print(req.text)
            return None

        result={}
        soep=Soup(req.text,'html.parser')
        bid_tag=soep.find(text="Bid")
        ask_tag=soep.find(text="Ask")

        try:
            bids=[utils.yahoo_float(i) for i in bid_tag.parent.parent.next_sibling.contents[0].get_text().split(" x ")]
            asks=[utils.yahoo_float(i) for i in ask_tag.parent.parent.next_sibling.contents[0].get_text().split(" x ")]
        except:
            print("Error in calling get_text() function.")
            return None

        result['bid']=bids[0]
        result['bid_volume']=bids[1]
        result['ask']=asks[0]
        result['ask_volume']=asks[1]

        return result

    def get_bid_price(self,ticker):
        returns the lates bid price of the ticker stock
        return self.get_bid_and_ask(ticker)['bid']

    def get_ask_price(self,ticker):
        returns the lates bid price of the ticker stock
        return self.get_bid_and_ask(ticker)['ask']

    def get_gainers(self):
        url=self.base_url+"gainers"
        req=requests.get(url)
        empty_df=pd.DataFrame()
        
        if not req.status_code==200:
            return empty_df

        soep=Soup(req.text,'html.parser')
        regex=re.compile('.*simpTblRow.*')
        all_results=soep.find_all("tr",{"class":regex})

        symbols=[]
        for res in all_results:
            symbols.append(res.find('a').get_text())

        if not (len(symbols)==len(all_results)):
            print("Web scraping error: length of symbols not equal to length of other colums from the Yahoo website.")
            return empty_df
        
        cols=["Name","Price (Intraday)","Change","% Change","Volume","Avg Vol (3 month)","Market Cap","PE Ratio (TTM)"]
        types={"Symbol":str,"Name":str,"Price (Intraday)":float,"Change":float,"% Change":str,"Volume":str,"Avg Vol (3 month)":str,"Market Cap":str,"PE Ratio (TTM)":str}
        pd_dict={"Symbol":symbols}

        for col in cols:
            pd_dict[col]=[]

        for i in range(len(all_results)):
            for col in cols:
                det_res=all_results[i].find("td",{"aria-label":col})
                if det_res==None:
                    print("While scraping, no results where found for the {} column".format(col))
                    return empty_df
                else:
                    pd_dict[col].append(det_res.get_text())

        for key in types:
            if types[key]==float:
                pd_dict[key]=[elem.replace(',','') for elem in pd_dict[key]]

        df=pd.DataFrame.from_dict(pd_dict)
        df=df.astype(types,copy=False)
        df.sort_values(by=["Change"],ascending=False,inplace=True)

        return df

    def get_symbols_best_gainers(self,number=5):
        df_gainers=self.get_gainers()
        if df_gainers.empty:
            return None
        best_gainers=df_gainers.head(number)
        return best_gainers["Symbol"].to_list()

    def get_names_best_gainers(self,number=5):
        df_gainers=self.get_gainers()
        if df_gainers.empty:
            return None
        best_gainers=df_gainers.head(number)
        return best_gainers["Name"].to_list()
'''


        