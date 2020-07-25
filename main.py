#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time as _time
import datetime as _datetime
import matplotlib.pyplot as _plt
import pandas as _pd
from trade_logic import Stocks
import utils


STARTING_BALANCE=10000
stocks=Stocks(STARTING_BALANCE)
OUTPUT_DIR_LOG="./output/ALGO_TRADING_LOG_{}.txt".format(utils.date_now_filename())
OUTPUT_DIR_PLOTS="./output/plots"

utils.mkdir_p(OUTPUT_DIR_PLOTS)
ronde=-1
while True:
    ronde+=1
    MODE="STATUS INFORMATION   -:-"
    utils.write_output("-"*220,OUTPUT_DIR_LOG)
    utils.write_output_formatted(MODE,"Current Balance: ${}".format(stocks.balance),OUTPUT_DIR_LOG)

    utils.write_output_formatted(MODE,"Virtual Total  : ${}".format(stocks.virtual_total),OUTPUT_DIR_LOG)

    utils.write_output_formatted(MODE,"Plotting bought stocks data...",OUTPUT_DIR_LOG)
    stocks.plot_bought_stock_data(OUTPUT_DIR_PLOTS)

    if not bool(stocks.current_stocks):
        utils.write_output_formatted(MODE,"Currently no stocks are in posession.",OUTPUT_DIR_LOG)
    else:
        utils.write_output_formatted(MODE,"Stocks in posession: {}".format(utils.write_stocks(stocks.current_stocks)),OUTPUT_DIR_LOG)

    if (ronde==0): # check whether we want to buy new stocks, and if true, buy them
        MODE="CHECK TO BUY         -:-"
        if not stocks.check_to_buy(OUTPUT_DIR_LOG):
            utils.write_output_formatted(MODE,"Not buying anything because of error.",OUTPUT_DIR_LOG)

    elif ronde==1: # check whether we want to sell any of our current stocks, and if true, sell them
        stocks.check_to_sell(OUTPUT_DIR_LOG)
        ronde=-1








