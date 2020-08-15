#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time as _time
import datetime as _datetime
import matplotlib.pyplot as _plt
import pandas as pd
from trade_logic import Stocks
from yahoo_scraping import YahooScraper
import utils
import threading
import argparse
import shutil as sh

OUTPUT_DIR="./output/"
OUTPUT_DIR_LOG=OUTPUT_DIR+"ALGO_TRADING_LOG_{}.txt".format(utils.date_now_filename())
OUTPUT_DIR_PLOTS=OUTPUT_DIR+"plots"
OUTPUT_DIR_STATUS=OUTPUT_DIR+"ALGO_STATUS_LOG_{}.txt".format(utils.date_now_filename())
OUTPUT_DIR_PLOTDATA=OUTPUT_DIR+"ALGO_PLOTDATA_LOG_{}.txt".format(utils.date_now_filename())
OUTPUT_DIR_OVERVIEW=OUTPUT_DIR+"ALGO_OVERVIEW_LOG_{}.txt".format(utils.date_now_filename())
ENDING_CONFIG_PATH=OUTPUT_DIR+"ALGO_ENDING_CONFIG_{}.txt".format(utils.date_now_filename())

# Parse input arguments
parser=argparse.ArgumentParser(description="GLENNY's argument parser")
parser.add_argument('--config_file','-c',type=str,help='Configuration file in JSON format containing initial state.',default="./config.json")
args=parser.parse_args()

def start_algorithm(config_file=None):
    # Initialize stocks object with configuration values
    if not config_file:
        config_file=args.config_file
    init_val=utils.read_initial_values(config_file)
    stocks=Stocks(balance=init_val["balance"],
                    current_stocks=init_val["current_stocks"],
                    previously_checked_stocks=init_val["previously_checked_stocks"],
                    bought_stock_data=init_val["bought_stock_data"],
                    current_status=init_val["current_status"],
                    tosell=init_val["tosell"])

    # Clean output directory
    utils.clean_output(OUTPUT_DIR,OUTPUT_DIR_PLOTS)

    # Set initial values
    stock_market_open=True
    ronde=-1
    #counter=0

    while stock_market_open:
        ronde+=1
        MODE="STATUS INFORMATION   -:-"

        # Write current overview
        utils.write_json(stocks.get_overview(),OUTPUT_DIR_OVERVIEW)

        # Write current status per owned stock
        utils.write_json(stocks.current_status,OUTPUT_DIR_STATUS)
        
        # Write plotdata per owned stock
        utils.write_plotdata(stocks.bought_stock_data,OUTPUT_DIR_PLOTDATA)

        # Logging...
        utils.write_output("-"*220,OUTPUT_DIR_LOG)
        utils.write_output_formatted(MODE,"Current Balance: ${}".format(stocks.balance),OUTPUT_DIR_LOG)
        utils.write_output_formatted(MODE,"Plotting bought stocks data...",OUTPUT_DIR_LOG)
        stocks.plot_bought_stock_data(OUTPUT_DIR_PLOTS)

        if not bool(stocks.current_stocks):
            utils.write_output_formatted(MODE,"Currently no stocks are in possession.",OUTPUT_DIR_LOG)
        else:
            utils.write_output_formatted(MODE,"Stocks in posession: {}".format(utils.write_stocks(stocks.current_stocks)),OUTPUT_DIR_LOG)

        # Read and save whether the user has ordered manually to sell a certain stock, and if true, sell it
        commands_log=utils.get_latest_log("COMMANDS")
        commands=utils.read_commands(commands_log)
        stocks.tosell=commands['tickers']
        stocks.hard_sell_check(OUTPUT_DIR_LOG)


        # Check whether we want to buy new stocks, and if true, buy them
        if (ronde==0):  
            MODE="CHECK TO BUY         -:-"
            if not stocks.check_to_buy(OUTPUT_DIR_LOG):
                utils.write_output_formatted(MODE,"Not buying anything because of error.",OUTPUT_DIR_LOG)

        # Check whether we want to sell any of our current stocks, and if true, sell them
        elif ronde==1:  
            stocks.check_to_sell(OUTPUT_DIR_LOG)
            ronde=-1

        # Check if all markets are closed
        scraper=YahooScraper()
        if scraper.all_markets_closed(stocks.current_stocks) or ("STOPALGORITHM" in commands['commands']):
        #counter+=1
        #if (counter==7) or ("STOPALGORITHM" in commands['commands']):
            print("GLENNY terminating")
            stocks.current_stocks=utils.close_markets(stocks.current_status)
            utils.write_json(stocks.get_overview(market_open=False),OUTPUT_DIR_OVERVIEW)
            utils.write_config(stocks,ENDING_CONFIG_PATH)
            sh.copy(ENDING_CONFIG_PATH,"./latest_state.json")
            break

    return True











