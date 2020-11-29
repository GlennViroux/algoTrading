#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import datetime,timedelta
import pandas as pd
import numpy as np
import requests
import json

class YahooAPI:
    def __init__(self):
        self.base_url = "https://query1.finance.yahoo.com"

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

        if isinstance(start,str):
            start_datetime=datetime.strptime(start,'%Y/%m/%d-%H:%M:%S')
        else:
            start_datetime=start
        if isinstance(end,str):
            end_datetime=datetime.strptime(end,'%Y/%m/%d-%H:%M:%S')
        else:
            end_datetime=end

        first_unix=datetime(1970,1,1)
        
        start_unix=int((start_datetime-first_unix).total_seconds())-2*3600
        end_unix=int((end_datetime-first_unix).total_seconds())-2*3600

        if logger:
            logger.debug("Ticker: {}. Start unix: {}, end unix: {}".format(ticker,start_unix,end_unix),extra={'function':FUNCTION})

        #print(url+"?"+"symbol="+ticker+"&"+"period1="+str(start_unix)+"&"+"period2="+str(end_unix)+"&"+"interval="+interval+"&"+"includePrePost="+"false")
        try:
            req=requests.get(url,params={'symbol':ticker,'period1':start_unix,'period2':end_unix,'interval':interval,'includePrePost':'false'})
        except:
            if logger:
                logger.error("Ticker: {}. Error occured while performing request to yahoo API.".format(ticker),extra={'function':FUNCTION})
            return pd.DataFrame

        if req.status_code!=200:
            if logger:
                logger.debug("Ticker: {}. No valid response was received from the yahoo query ({}). Status code: {}".format(ticker,url,req.status_code),extra={'function':FUNCTION})
            print(req.text)
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

    def calculate_EMAs( 
        self,
        ticker,
        df,
        mytype,
        period,
        label,
        logger=None):

        FUNCTION="calculate_EMAs"
        '''
        returns dataframe:
        'index' | 'timestamps' | 'EMA'
        EMA calculated with an interval of interval and a data period of period
        '''
        if df.dropna().empty:
            return df.dropna()
        
        timestamps=df.timestamps
        points=df[mytype]

        EMAs=[]

        # 1) Calculate first SMA
        if len(timestamps)<=period:
            logger.debug("Ticker: {}. Length of data from yahooAPI ({}) was smaller than requested EMA period ({}).".format(ticker,len(timestamps),period),extra={'function':FUNCTION})
            return pd.DataFrame

        i=0
        point = points[i]
        while np.isnan(point):
            EMAs.append(np.nan)
            i+=1
            point=points[i]

        in_process=True
        initial_points=[]
        while in_process:
            if not np.isnan(points[i]):
                initial_points.append(points[i])
            EMAs.append(np.nan)
            i+=1

            if len(initial_points)==period:
                in_process=False
        
        SMA = np.mean(initial_points)
        
        # 2) Calculate first EMA
        EMA_init=points[i]*(2/(1+period)) + SMA*(1-2/(1+period))
        EMAs.append(EMA_init)
        i+=1

        # 3) Calculate other EMAs
        length=len(timestamps)
        for j in range(i,length):
            EMA=points[j]*(2/(1+period)) + EMAs[j-1]*(1-2/(1+period))
            EMAs.append(EMA)

        # 4) Convert to to pandas df
        result={'timestamps':timestamps,label:EMAs}
        df=pd.DataFrame(result)

        return df.set_index('timestamps')

    def calculate_SAR(self,ticker,df):
        '''
        calculate parabolic SAR
        '''
        if df.empty:
            return df

        df = df.sort_values('timestamps')

        timestamps = df.timestamps
        highs = df.high
        opens = df.open
        closes = df.close
        lows = df.low

        # Initialize values
        alpha_prev = 0.02
        if opens[0]>closes[0]:
            trend_prev = "down"
            EP_prev = lows[0]
            SAR_prev = lows[0]
        else:
            trend_prev = "up"
            EP_prev = highs[0]
            SAR_prev = highs[0]

        results = [SAR_prev]

        # Caluclate SAR for each timestamp
        for i in range(1,len(timestamps)):
            if trend_prev=='up':
                high = highs[i]
                low = lows[i]

                EP_new = max(EP_prev,high)
                alpha_new = alpha_prev
                if high>EP_prev and alpha_prev<=0.18:
                        alpha_new+=0.02

                SAR_new = SAR_prev + alpha_prev*(EP_prev-SAR_prev)

                trend_new = trend_prev
                if SAR_new>=low:
                    trend_new = 'down'
                    alpha_new = 0.02
                    EP_new = low
                    SAR_new = max(high,EP_prev)

            elif trend_prev=='down':
                high = highs[i]
                low = lows[i]

                EP_new = min(EP_prev,low)
                alpha_new = alpha_prev
                
                if low<EP_prev and alpha_prev<=0.18:
                        alpha_new+=0.02
                
                SAR_new = SAR_prev - alpha_prev*(SAR_prev-EP_prev)

                trend_new = trend_prev
                if SAR_new<=high:
                    trend_new = 'up'
                    alpha_new = 0.02
                    EP_new = high
                    SAR_new = min(low,EP_prev)

            results.append(SAR_new)
            trend_prev = trend_new
            EP_prev = EP_new
            alpha_prev = alpha_new
            SAR_prev = SAR_new

        df = pd.DataFrame({'timestamps':timestamps,'SAR':results})

        return df.set_index('timestamps')

    def calculate_oscillators(self,ticker,df,logger=None):
        '''
        calculate the fast and slow oscillators
        '''        
        if df.empty:
            return df
            
        df = df.sort_values('timestamps')

        timestamps = df.timestamps
        highs = df.high
        closes = df.close
        lows = df.low

        N = 140
        # Initialize slow results
        slow_results = [np.nan for i in range(1,N)]

        # Calculate slow results for each timestamp
        for i in range(N,len(timestamps)+1):
            LN = min(lows[i-N:i])
            HN = max(highs[i-N:i])
            C = closes[i-1]

            P_K = 100*(C-LN)/(HN-LN)
            slow_results.append(P_K)

        df = pd.DataFrame(list(zip(timestamps,slow_results)),columns=['timestamps','slow_oscillator'])

        # Calculate fast results
        df_fast_oscillator = self.calculate_EMAs(ticker,df,'slow_oscillator',30,'fast_oscillator',logger)

        df_result = pd.concat([df.set_index('timestamps'),df_fast_oscillator],axis=1)

        return df_result

    def calculate_MACD(self,ticker,df,logger=None):
        '''
        Calculate the MACD
        '''
        if df.empty:
            return df
            
        df = df.sort_values('timestamps')

        df_EMA12=self.calculate_EMAs(ticker,df,'close',12,'EMA12',logger=logger)
        df_EMA26=self.calculate_EMAs(ticker,df,'close',26,'EMA26',logger=logger)
        if df_EMA12.empty or df_EMA26.empty:
            if logger:
                logger.debug("Ticker {} and EMA period {}: no valid data from calculating the EMAs was received.".format(ticker,1),extra={'function':FUNCTION})
            return pd.DataFrame

        df_MACD = pd.concat([df_EMA12,df_EMA26],axis=1).reset_index()
        df_MACD['MACD_line'] = df_MACD.EMA12-df_MACD.EMA26

        signal_line = self.calculate_EMAs(ticker,df_MACD,'MACD_line',9,'signal_line',logger)
        df_MACD = pd.concat([df_MACD.set_index('timestamps'),signal_line],axis=1)
        df_MACD['MACD_histo'] = df_MACD.MACD_line-df_MACD.signal_line

        return df_MACD[['MACD_line','signal_line','MACD_histo']]

    def calculate_RSI(self,ticker,df,logger=None):
        '''
        Calculate the RSI
        '''
        if df.empty:
            return df
            
        df = df.sort_values('timestamps')

        period = 14

        if len(df)<=period:
            return pd.DataFrame

        df_rsi = df
        df_rsi['diff'] = df.close - df.open
        df_rsi['gain'] = df_rsi['diff'].apply(lambda x: x if x>=0 else 0)
        df_rsi['loss'] = df_rsi['diff'].apply(lambda x: x if x<0 else 0)

        gains = list(df_rsi.gain)
        losses = list(df_rsi.loss)
        RSIs = [np.nan for i in range(period)]
        for i in range(period,len(gains)):
            avg_gain = np.mean(gains[i-14:i])
            avg_loss = -np.mean(losses[i-14:i])
            if avg_loss==0:
                new_RSI=100
            else:
                new_RSI = 100 - (100/(1+(avg_gain/avg_loss)))
            RSIs.append(new_RSI)

        df_rsi['RSI'] = RSIs

        df_rsi = df_rsi.set_index('timestamps')

        return df_rsi[['RSI']]



    def get_data(self,ticker,start,end,interval,period_small_EMA,period_big_EMA,logger=None):
        FUNCTION='get_data'
        '''
        returns dataframe:
        'index' | 'timestamps' | 'open' | 'close' | 'low' | 'high' | 'volume' | 'smallEMA' | 'bigEMA'
        '''
        df_data=self.get_historic_data(ticker,start,end,interval,logger=logger)
        if df_data.empty:
            return df_data
        #df_base=df_data.set_index('timestamps')

        df_smallEMA=self.calculate_EMAs(ticker,df_data,'close',period_small_EMA,'smallEMA',logger=logger)
        if df_smallEMA.empty:
            if logger:
                logger.debug("Ticker {} and EMA period {}: no valid data from calculating the EMAs was received.".format(ticker,period_small_EMA),extra={'function':FUNCTION})
            return pd.DataFrame

        df_bigEMA=self.calculate_EMAs(ticker,df_data,'close',period_big_EMA,'bigEMA',logger=logger)
        if df_bigEMA.empty:
            if logger:
                logger.debug("Ticker {} and EMA period {}: no valid data from calculating the EMAs was received.".format(ticker,period_big_EMA),extra={'function':FUNCTION})
            return pd.DataFrame

        df_simpleEMA=self.calculate_EMAs(ticker,df_data,'close',1,'simpleEMA',logger=logger)
        if df_simpleEMA.empty:
            if logger:
                logger.debug("Ticker {} and EMA period {}: no valid data from calculating the EMAs was received.".format(ticker,1),extra={'function':FUNCTION})
            return pd.DataFrame

        df_advancedEMA=self.calculate_EMAs(ticker,df_data,'close',20,'advancedEMA',logger=logger)
        if df_simpleEMA.empty:
            if logger:
                logger.debug("Ticker {} and EMA period {}: no valid data from calculating the EMAs was received.".format(ticker,1),extra={'function':FUNCTION})
            return pd.DataFrame

        df_SAR=self.calculate_SAR(ticker,df_data)
        if df_SAR.empty:
            if logger:
                logger.debug("Ticker {}: Unable to calculate parabolic SAR.".format(ticker),extra={'function':FUNCTION})
            return pd.DataFrame

        df_oscillators=self.calculate_oscillators(ticker,df_data,logger)
        if df_oscillators.empty:
            if logger:
                logger.debug("Ticker {}: Unable to calculate fast and slow oscillators.".format(ticker),extra={'function':FUNCTION})
            return pd.DataFrame

        df_MACD=self.calculate_MACD(ticker,df_data,logger)
        if df_MACD.empty:
            if logger:
                logger.debug("Ticker {}: Unable to calculate the MACD indicator.".format(ticker),extra={'function':FUNCTION})
            return pd.DataFrame

        df_RSI=self.calculate_RSI(ticker,df_data,logger)
        if df_RSI.empty:
            if logger:
                logger.debug("Ticker {}: Unable to calculate the RSI.".format(ticker),extra={'function':FUNCTION})
            return pd.DataFrame

        df=pd.concat([
            df_data.set_index('timestamps'),
            df_smallEMA,
            df_bigEMA,
            df_simpleEMA,
            df_advancedEMA,
            df_SAR,
            df_oscillators,
            df_MACD,
            df_RSI
            ],axis=1,join='outer').reset_index()
        df.drop('index',axis=1,inplace=True,errors='ignore')
        df.sort_values("timestamps",inplace=True)

        return df











