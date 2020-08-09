#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time as _time
import datetime as _datetime
import matplotlib.pyplot as _plt
import pandas as _pd
from trade_logic import Stocks
import main_restful_api
import utils
import threading


STARTING_BALANCE=10000
stocks=Stocks(STARTING_BALANCE)
OUTPUT_DIR="./output/"
OUTPUT_DIR_LOG=OUTPUT_DIR+"ALGO_TRADING_LOG_{}.txt".format(utils.date_now_filename())
OUTPUT_DIR_PLOTS=OUTPUT_DIR+"plots"
OUTPUT_DIR_STATUS=OUTPUT_DIR+"ALGO_STATUS_LOG_{}.txt".format(utils.date_now_filename())
OUTPUT_DIR_PLOTDATA=OUTPUT_DIR+"ALGO_PLOTDATA_LOG_{}.txt".format(utils.date_now_filename())
OUTPUT_DIR_OVERVIEW=OUTPUT_DIR+"ALGO_OVERVIEW_LOG_{}.txt".format(utils.date_now_filename())

# Clean output directory
utils.clean_output(OUTPUT_DIR,OUTPUT_DIR_PLOTS)

# Get server running in daemon thread
s=threading.Thread(target=main_restful_api.start,args=(),daemon=True)
s.start()

ronde=-1
while True:
    ronde+=1
    MODE="STATUS INFORMATION   -:-"

    # 1) Write current overview
    utils.write_json(stocks.get_overview(),OUTPUT_DIR_OVERVIEW)

    # 2) Write current status per owned stock
    utils.write_json(stocks.current_status,OUTPUT_DIR_STATUS)
    
    # 3) Write plotdata per owned stock
    utils.write_plotdata(stocks.bought_stock_data,OUTPUT_DIR_PLOTDATA)

    # 4) Logging...
    utils.write_output("-"*220,OUTPUT_DIR_LOG)
    utils.write_output_formatted(MODE,"Current Balance: ${}".format(stocks.balance),OUTPUT_DIR_LOG)
    utils.write_output_formatted(MODE,"Virtual Total  : ${}".format(stocks.virtual_total),OUTPUT_DIR_LOG)
    utils.write_output_formatted(MODE,"Plotting bought stocks data...",OUTPUT_DIR_LOG)
    stocks.plot_bought_stock_data(OUTPUT_DIR_PLOTS)

    if not bool(stocks.current_stocks):
        utils.write_output_formatted(MODE,"Currently no stocks are in possession.",OUTPUT_DIR_LOG)
    else:
        utils.write_output_formatted(MODE,"Stocks in posession: {}".format(utils.write_stocks(stocks.current_stocks)),OUTPUT_DIR_LOG)

    # 5) Read and save whether the user has ordered manually to sell a certain stock, and if true, sell it
    selldata_log=utils.get_latest_log("TOSELL")
    stocks.tosell=utils.read_tosell_data(selldata_log)
    stocks.hard_sell_check(OUTPUT_DIR_LOG)

    # 6) Check whether we want to buy new stocks, and if true, buy them
    if (ronde==0):  
        MODE="CHECK TO BUY         -:-"
        if not stocks.check_to_buy(OUTPUT_DIR_LOG):
            utils.write_output_formatted(MODE,"Not buying anything because of error.",OUTPUT_DIR_LOG)

    # 7) Check whether we want to sell any of our current stocks, and if true, sell them
    elif ronde==1:  
        stocks.check_to_sell(OUTPUT_DIR_LOG)
        ronde=-1








