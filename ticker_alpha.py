#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests as requests
import datetime as _datetime
import pandas as pd
from base_alpha import AlphaAPI

class Alpha(AlphaAPI):

    def last_price(self):
        return self.get_last_price()

    def last_data(self,interval,outputsize='compact'):
        return self.get_time_series_intraday(interval,outputsize)

    def EMAs(self,interval,time_period,series_type):
        '''
        interval : 1min, 5min, 15min, 30min, 60min, daily, weekly, monthly
        time_period : integer
        series_type : close, open, high, low
        '''
        return self.get_EMAs(interval,time_period,series_type)

    def EMA(self,interval,time_period,series_type):
        return self.get_EMA(interval,time_period,series_type)