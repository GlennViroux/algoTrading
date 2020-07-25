#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests as _requests
import datetime as _datetime
import pandas as _pd
import time as _time

MAX_RETRY_PER_SYMBOL=3

class AlphaAPI():
    def __init__(self,symbol,apikey):
        self.symbol=symbol.upper()
        self.apikey=apikey
        self.base_url='https://www.alphavantage.co/query'
        self.info=None

    def get_time_series_intraday(self,interval,outputsize="compact",datatype="json"):
        params={}
        params["function"]="TIME_SERIES_INTRADAY"
        params["symbol"]=self.symbol
        params["interval"]=interval
        params["outputsize"]=outputsize
        params["apikey"]=self.apikey
        params["datatype"]=datatype

        response=_requests.get(self.base_url,params=params)

        if (response.status_code!=200):
            print("ERROR: Response status code: ",response.status_code)
            raise RuntimeError("ERROR: No valid response was received from the AlphaVantage API.")

        data=response.json()

        tag=f"Time Series ({interval})"

        try:
            data_per_timestamp=data[tag]
        except KeyError:
            print(response.text)
            raise RuntimeError("ERROR: No valid response was received from the AlphaVantage API.")
        

        data_dict={"timestamps":[],"opens":[],"highs":[],"lows":[],"closes":[],"volumes":[]}
        for timestamp in data_per_timestamp:
            data_dict["timestamps"].append(_pd.to_datetime(timestamp))
            data_dict["opens"].append(float(data_per_timestamp[timestamp]["1. open"]))
            data_dict["highs"].append(float(data_per_timestamp[timestamp]["2. high"]))
            data_dict["lows"].append(float(data_per_timestamp[timestamp]["3. low"]))
            data_dict["closes"].append(float(data_per_timestamp[timestamp]["4. close"]))
            data_dict["volumes"].append(float(data_per_timestamp[timestamp]["5. volume"]))

        df=_pd.DataFrame(data_dict)

        return df

    def get_global_quote(self,datatype="json"):
        params={}
        params["function"]="GLOBAL_QUOTE"
        params["symbol"]=self.symbol
        params["apikey"]=self.apikey

        response=_requests.get(self.base_url,params=params)

        if (response.status_code!=200):
            print("ERROR: Response status code: ",response.status_code)
            raise RuntimeError("ERROR: No valid response was received from the AlphaVantage API.")

        data=response.json()

        try:
            stock_data=data["Global Quote"]
            return stock_data
        except KeyError:
            print(response.text)
            raise RuntimeError("ERROR: Wrong API call for Global Quote data.")


    def get_last_price(self,datatype='json'):
        return self.get_global_quote(datatype=datatype)
        #return self.get_global_quote(datatype=datatype)['02. open']

    
    def get_EMAs(self,interval,time_period,series_type,outputsize="compact",datatype="json"):
        '''
        Returns a dataframe:
            index | timestamps | EMA
        '''
        params={}
        params["function"]="EMA"
        params["symbol"]=self.symbol
        params["interval"]=interval
        params["series_type"]=series_type
        params["time_period"]=time_period
        params["outputsize"]=datatype
        params["apikey"]=self.apikey

        success=False
        for retry_cnt in range(MAX_RETRY_PER_SYMBOL):
            
            response=_requests.get(self.base_url,params=params)

            if (response.status_code!=200):
                _time.sleep(0.2)
            else:
                success=True
                break

        if not success:
            print("ERROR: Response status code: ",response.status_code)
            raise RuntimeError("ERROR: No valid response was received from the AlphaVantage API on count {}.".format(retry_cnt))

        data=response.json()


        tag=f"Technical Analysis: EMA"

        try:
            data_per_timestamp=data[tag]
        except KeyError:
            print(response.text)
            raise RuntimeError("ERROR: No valid response was received from the AlphaVantage API.")
        
        data_dict={"timestamps":[],"EMA":[]}
        for timestamp in data_per_timestamp:
            data_dict["timestamps"].append(_pd.to_datetime(timestamp))
            data_dict["EMA"].append(float(data_per_timestamp[timestamp]["EMA"]))

        df=_pd.DataFrame(data_dict)
        df.sort_values(by='timestamps',axis=0,inplace=True)

        return df

    def get_EMA(self,interval,time_period,series_type,outputsize="compact",datatype="json"):
        df=self.get_EMAs(interval,time_period,series_type,outputsize,datatype)

        return df.iloc[-1]['EMA']
