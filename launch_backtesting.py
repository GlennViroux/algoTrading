from backtesting import BackTesting
from datetime import datetime,timedelta

import argparse
import utils
import time
import os

def main(days=None,number=None,sell_criterium=None,stocks=None,start_date=None,upload_results=False):
    start_time = time.time()
    parser = argparse.ArgumentParser()
    parser.add_argument('-d','--days_in_past',default=None,type=int)
    parser.add_argument('-b','--start_date',default=None)
    parser.add_argument('-n','--number_of_stocks',default=1,type=int)
    parser.add_argument('-c','--sell_criterium',default='EMA',choices=['EMA','price','simple','advanced'],type=str)
    parser.add_argument('-s','--stocks',required=False)
    parser.add_argument('-u','--upload_results',action='store_true')
    args = parser.parse_args()

    if args.upload_results:
        upload_results = True

    if not days and not start_date:
        if args.days_in_past and args.start_date:
            raise Exception("Both number of days and start date are provided.")
        elif args.days_in_past:
            start = datetime.now() - timedelta(days=args.days_in_past) # max is 46 days
        elif args.start_date:
            start = start_date=datetime.strptime(args.start_date,"%Y/%m/%d-%H:%M:%S")
    elif not days and start_date:
        if isinstance(start_date,str):
            start_date=datetime.strptime(start_date,"%Y/%m/%d-%H:%M:%S")
        start = start_date
    elif days and not start_date:
        start = datetime.now() - timedelta(days=days) # max is 46 days
    else:
        raise Exception("Both number of days and start date are provided.")

    if not number:
        number = args.number_of_stocks
    if not sell_criterium:
        sell_criterium = args.sell_criterium
    if not stocks and args.stocks:
            stocks = args.stocks.split(',')
    
    
    b = BackTesting(start,number,sell_criterium,stocks)
    for stock in b.monitored_stocks:
        b.calculate_result(stock)
    
    b.append_csv()
    b.get_all_stats()
    if upload_results:
        b.upload_stats()
        b.upload_results()

    delta = time.time()-start_time
    b.update_yql_calls_file(delta)

    print("GLENNY launch backtesting done")


if __name__=='__main__':
    main()

