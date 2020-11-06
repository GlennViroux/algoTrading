from backtesting import BackTesting
from datetime import datetime,timedelta

import argparse
import utils
import time
import os

def main(days=None,number=None,sell_criterium=None,stocks=None):
    start_time = time.time()
    parser = argparse.ArgumentParser()
    parser.add_argument('-d','--days_in_past',default=40,type=int)
    parser.add_argument('-n','--number_of_stocks',default=1,type=int)
    parser.add_argument('-c','--sell_criterium',default='EMA',choices=['EMA','price'],type=str)
    parser.add_argument('-s','--stocks',required=False)
    args = parser.parse_args()

    if not days:
        days = args.days_in_past
    if not number:
        number = args.number_of_stocks
    if not sell_criterium:
        sell_criterium = args.sell_criterium
    if not stocks and args.stocks:
            stocks = args.stocks.split(',')
    
    start = datetime.now() - timedelta(days=days) # max is 46 days
    b = BackTesting(start,number,sell_criterium,stocks)
    for stock in b.monitored_stocks:
        b.calculate_result(stock)
    
    b.append_csv()
    b.upload_results()
    b.get_all_stats()

    delta = time.time()-start_time
    b.update_yql_calls_file(delta)


if __name__=='__main__':
    main()

