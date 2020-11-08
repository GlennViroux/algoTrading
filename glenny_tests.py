
from launch_backtesting import main 
from datetime import datetime,timedelta

start = datetime.strptime("2020/10/02-15:00:00",'%Y/%m/%d-%H:%M:%S')
dates = [start+timedelta(days=i) for i in range(5,24)]

for date in dates:
    print(date)
    main(number=5,sell_criterium='simple',start_date=date)