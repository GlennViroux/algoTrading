
from yahoo_api import YahooAPI
from datetime import datetime,timedelta

yah = YahooAPI()
ticker = 'MSFT'
start = datetime(2020,10,20,0,0,0)
end = start + timedelta(days=1)
interval = '5m'
period_small_EMA=3
period_big_EMA=5
df = yah.get_data(ticker,start,end,interval,period_small_EMA,period_big_EMA)

print(df.head(40))