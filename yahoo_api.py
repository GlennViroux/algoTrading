#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import datetime,timedelta
import pandas as pd
import numpy as np
import requests
import json

class YahooAPI:
    def __init__(self):
        self.base_url = "https://query1.finance.yahoo.com/"

    def get_historic_data(self,ticker,start,end,interval,logger=None):
        FUNCTION='get_historic_data'
        '''
        Returns DataFrame:
        'index' | 'timestamps' | 'open' | 'close' | 'low' | 'high' | 'volume'

        start and end inputs given in CEST timezone
        timestamps in df are given in UTC timezone
        '''
        url=self.base_url+"/v8/finance/chart/{}".format(ticker)

        if logger:
            logger.debug("Ticker: {}. Getting data from {} until {}".format(ticker,start,end),extra={'function':FUNCTION})

        start_datetime=datetime.strptime(start,'%Y/%m/%d-%H:%M:%S')
        end_datetime=datetime.strptime(end,'%Y/%m/%d-%H:%M:%S')

        first_unix=datetime(1970,1,1)
        
        start_unix=int((start_datetime-first_unix).total_seconds())-2*3600
        end_unix=int((end_datetime-first_unix).total_seconds())-2*3600

        if logger:
            logger.debug("Ticker: {}. Start unix: {}, end unix: {}".format(ticker,start_unix,end_unix),extra={'function':FUNCTION})

        #print(url+"?"+"symbol="+ticker+"&"+"period1="+str(start_unix)+"&"+"period2="+str(end_unix)+"&"+"interval="+interval+"&"+"includePrePost="+"true")
        req=requests.get(url,params={'symbol':ticker,'period1':start_unix,'period2':end_unix,'interval':interval,'includePrePost':'true'})

        if req.status_code!=200:
            if logger:
                logger.debug("Ticker: {}. No valid response was received from the yahoo query ({}).".format(ticker,url),extra={'function':FUNCTION})
            return pd.DataFrame

        json_data=json.loads(req.text)

        gmtoffset=int(json_data['chart']['result'][0]['meta']['gmtoffset'])

        try:
            timestamps = [first_unix+timedelta(seconds=int(t)+gmtoffset) for t in json_data['chart']['result'][0]['timestamp']]
        except KeyError:
            if logger:
                logger.debug("Ticker: {}. No valid data (KeyError when getting timestamps) was obtained from the yahooAPI".format(ticker),extra={'function':FUNCTION})
            return pd.DataFrame

        df_dict={'timestamps':timestamps,
                 'open':json_data['chart']['result'][0]['indicators']['quote'][0]['open'],
                 'close':json_data['chart']['result'][0]['indicators']['quote'][0]['close'],
                 'low':json_data['chart']['result'][0]['indicators']['quote'][0]['low'],
                 'high':json_data['chart']['result'][0]['indicators']['quote'][0]['high'],
                 'volume':json_data['chart']['result'][0]['indicators']['quote'][0]['volume']}

        df=pd.DataFrame(data=df_dict)
        df.dropna(inplace=True)
        df.reset_index(inplace=True)
        df.drop('index',axis=1,inplace=True,errors='ignore')

        return df

    def calculate_EMAs(self,ticker,start,end,interval,period,smallEMA=True,df_historic_data=pd.DataFrame,logger=None):
        FUNCTION="calculate_EMAs"
        '''
        returns dataframe:
        'index' | 'timestamps' | 'EMA'
        EMA calculated with an interval of interval and a data period of period
        '''
        df=df_historic_data
        if df.empty:
            df=self.get_historic_data(ticker,start,end,interval,logger)
        
        timestamps=df.timestamps
        closes=df.close

        EMAs=[]

        # 1) Calculate first SMA
        if len(timestamps)<=period:
            logger.debug("Ticker: {}. Length of data from yahooAPI ({}) was smaller than requested EMA period ({}).".format(ticker,len(timestamps),period),extra={'function':FUNCTION})
            return pd.DataFrame

        SMA=0
        for i in range(period):
            SMA+=(closes[i]/period)
            EMAs.append(np.nan)
        
        # 2) Calculate first EMA
        EMA_init=closes[period]*(2/(1+period)) + SMA*(1-2/(1+period))
        EMAs.append(EMA_init)

        # 3) Calculate other EMAs
        length=len(timestamps)
        for i in range(period+1,length):
            EMA=closes[i]*(2/(1+period)) + EMAs[i-1]*(1-2/(1+period))
            EMAs.append(EMA)

        # 4) Converto to pandas df
        tag='bigEMA'
        if smallEMA:
            tag='smallEMA'

        result={'timestamps':timestamps,tag:EMAs}
        df=pd.DataFrame(result)

        return df

    def get_data(self,ticker,start,end,interval,period_small_EMA,period_big_EMA,logger=None):
        FUNCTION='get_data'
        '''
        returns dataframe:
        'index' | 'timestamps' | 'open' | 'close' | 'low' | 'high' | 'volume' | 'smallEMA' | 'bigEMA'
        '''
        df_data=self.get_historic_data(ticker,start,end,interval,logger=logger)
        if df_data.empty:
            return df_data
        df_base=df_data.set_index('timestamps')

        df_smallEMA=self.calculate_EMAs(ticker,start,end,interval,period_small_EMA,smallEMA=True,df_historic_data=df_data,logger=logger)
        if df_smallEMA.empty:
            if logger:
                logger.debug("Ticker {} and EMA period {}: no valid data from calculating the EMAs was received.".format(ticker,period_small_EMA),extra={'function':FUNCTION})
            return pd.DataFrame
        df_smallEMA=df_smallEMA.set_index('timestamps')

        df_bigEMA=self.calculate_EMAs(ticker,start,end,interval,period_big_EMA,smallEMA=False,df_historic_data=df_data,logger=logger)
        if df_bigEMA.empty:
            if logger:
                logger.debug("Ticker {} and EMA period {}: no valid data from calculating the EMAs was received.".format(ticker,period_big_EMA),extra={'function':FUNCTION})
            return pd.DataFrame
        df_bigEMA=df_bigEMA.set_index('timestamps')

        df=pd.concat([df_base,df_smallEMA,df_bigEMA],axis=1,join='outer').reset_index()
        df.drop('index',axis=1,inplace=True,errors='ignore')
        df.sort_values("timestamps",inplace=True)

        return df











