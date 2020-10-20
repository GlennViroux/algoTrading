from backtesting import BackTesting
from datetime import datetime,timedelta
import utils
import time
import os

os.system('rm ./output/plots/*png')
start = datetime.now() - timedelta(days=40) # max is 46 days
b = BackTesting(start,20)
for stock in b.monitored_stocks:
    b.calculate_result(stock)
b.append_csv()

print(b.get_daily_YQL_calls())
print(b.get_hourly_YQL_calls())







