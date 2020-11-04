
from datetime import datetime
from backtesting import BackTesting

start = datetime.strptime("2020/10/01-00:00:00",'%Y/%m/%d-%H:%M:%S')
b = BackTesting(start,0,"price")

b.get_stats_param('drop_buying',-3)
b.get_stats_param('EMA_surface_min',-50)
b.get_stats_param('EMA_surface_plus',50,upper_threshold=True)