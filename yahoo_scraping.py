#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests as _requests
import pandas as _pd
from bs4 import BeautifulSoup as _Soup
import re
from utils import yahoo_float

class YahooScraper:
    def __init__(self):
        self.base_url="https://finance.yahoo.com/"

    def get_bid_and_ask(self,ticker):
        '''
        return {'bid':bid_price,'bid_volume'=bid_volume,'ask'=ask_price,'ask_volume'=ask_volume}
        '''
        url=self.base_url+"quote/{}".format(ticker.upper())
        try:
            req=_requests.get(url)
        except:
            return None

        if not req.status_code==200:
            print("Wrong status code.")
            print(req.status_code)
            print(req.text)
            return None

        result={}
        soep=_Soup(req.text,'html.parser')
        bid_tag=soep.find(text="Bid")
        ask_tag=soep.find(text="Ask")

        try:
            bids=[yahoo_float(i) for i in bid_tag.parent.parent.next_sibling.contents[0].get_text().split(" x ")]
            asks=[yahoo_float(i) for i in ask_tag.parent.parent.next_sibling.contents[0].get_text().split(" x ")]
        except:
            print("Error in calling get_text() function.")
            return None

        result['bid']=bids[0]
        result['bid_volume']=bids[1]
        result['ask']=asks[0]
        result['ask_volume']=asks[1]

        return result


    def get_bid_price(self,ticker):
        '''
        returns the lates bid price of the ticker stock
        '''
        return self.get_bid_and_ask(ticker)['bid']


    def get_ask_price(self,ticker):
        '''
        returns the lates bid price of the ticker stock
        '''
        return self.get_bid_and_ask(ticker)['ask']


    def get_gainers(self):
        url=self.base_url+"gainers"
        req=_requests.get(url)
        empty_df=_pd.DataFrame()
        
        if not req.status_code==200:
            return empty_df

        soep=_Soup(req.text,'html.parser')
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

        df=_pd.DataFrame.from_dict(pd_dict)
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

        