from backtesting import BackTesting
from datetime import datetime,timedelta

import argparse
import utils
import time
import os

def main(days=None,number=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('-d','--days_in_past',default=40,type=int)
    parser.add_argument('-n','--number_of_stocks',default=1,type=int)
    args = parser.parse_args()

    if not days:
        days = args.days_in_past
    if not number:
        number = args.number_of_stocks

    start = datetime.now() - timedelta(days=days) # max is 46 days
    b = BackTesting(start,number)
    for stock in b.monitored_stocks:
        b.calculate_result(stock)
    b.upload_to_drive()

    return "All good!"
    #return {'daily_calls':b.get_daily_YQL_calls(),'hourly_calls':b.get_hourly_YQL_calls()}

if __name__=='__main__':
    main()

