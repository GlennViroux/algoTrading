from backtesting import BackTesting
from datetime import datetime,timedelta

import argparse
import utils
import time
import os

parser = argparse.ArgumentParser()
parser.add_argument('-d','--days_in_past',default=40,type=int)
parser.add_argument('-n','--number_of_stocks',default=1,type=int)

args = parser.parse_args()

os.system('rm ./output/plots/*png')
start = datetime.now() - timedelta(days=args.days_in_past) # max is 46 days
b = BackTesting(start,args.number_of_stocks)
for stock in b.monitored_stocks:
    b.calculate_result(stock)
b.upload_to_drive()

print(b.get_daily_YQL_calls())
print(b.get_hourly_YQL_calls())
