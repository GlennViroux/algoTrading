#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import time
from datetime import datetime
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

def start_algorithm(config_file=None,fixed_rounds=None):
    FUNCTION='main'
    # Clean output directory
    utils.clean_output(OUTPUT_DIR,OUTPUT_DIR_PLOTS)

    # Configure logging
    logger=logging.getLogger("GLENNYlogger")
    c_handler=logging.StreamHandler()
    f_handler=logging.FileHandler(OUTPUT_DIR_LOG)
    logger.setLevel(logging.DEBUG)
    f_handler.setLevel(logging.DEBUG)
    c_handler.setLevel(logging.DEBUG)
    myFormat=logging.Formatter("[%(asctime)s] - [%(levelname)-8s] - [%(function)-30s] - %(message)s",datefmt="%Y/%m/%d-%H:%M:%S")
    f_handler.setFormatter(myFormat)
    c_handler.setFormatter(myFormat)
    logger.addHandler(f_handler)
    logger.addHandler(c_handler)

    logger.info("Starting algorithm.",extra={'function':FUNCTION})

    # Initialize stocks object with configuration values
    if not config_file:
        config_file=args.config_file

    logger.info("Reading initial values from config file: {}...".format(config_file),extra={'function':FUNCTION})
    init_val=utils.read_initial_values(config_file,logger=logger)
    logger.info("Read initial values from config file: {}".format(config_file),extra={'function':FUNCTION})

    stocks=Stocks(balance=init_val["balance"],
                    bought_stocks=init_val["bought_stocks"],
                    monitored_stocks=init_val["monitored_stocks"],
                    current_status=init_val["current_status"],
                    monitored_stock_data=init_val["monitored_stock_data"])

    # Check which stocks to monitor
    logger.info("Getting and initializing list of stocks to monitor...",extra={'function':FUNCTION})
    stocks.initialize_stocks(logger=logger,update_nasdaq_file=False)
    logger.info("Got and initialized stocks to monitor.",extra={'function':FUNCTION})

    # Set initial values
    stock_market_open=True
    counter=0

    while stock_market_open:
        # Write current overview
        logger.info("Writing overview...",extra={'function':FUNCTION})
        utils.write_json(stocks.get_overview(logger=logger),OUTPUT_DIR_OVERVIEW,logger=logger)
        logger.info("Written overview...",extra={'function':FUNCTION})

        # Write current status per monitored stock
        logger.info("Writing current status...",extra={'function':FUNCTION})
        utils.write_json(stocks.current_status,OUTPUT_DIR_STATUS,logger=logger)
        logger.info("Written current status",extra={'function':FUNCTION})

        # Read and save whether the user has ordered manually to sell a certain stock, and if true, sell it
        commands_log=utils.get_latest_log("COMMANDS",logger=logger)
        commands=utils.read_commands(commands_log,logger=logger)
        stocks.hard_sell_check(commands,OUTPUT_DIR_LOG,commands_log,logger=logger)

        # Loop through monitored stocks
        logger.info("Checking monitored stocks...",extra={'function':FUNCTION})
        for stock in stocks.monitored_stocks:
            stocks.check_monitored_stock(stock,logger=logger)
        logger.info("Checked all monitored stocks",extra={'function':FUNCTION})

        # Plot data per monitored stock
        logger.info("Plotting monitored stock data...",extra={'function':FUNCTION})
        stocks.plot_monitored_stock_data(OUTPUT_DIR_PLOTS,logger=logger)
        logger.info("Plotted all monitored stock data...",extra={'function':FUNCTION})

        # Check if all markets are closed
        if fixed_rounds:
            counter+=1
            if counter>fixed_rounds:
                logger.info("Terminating algorithm because of configured fixed rounds",extra={'function':FUNCTION})
                stocks.bought_stocks=utils.close_markets(stocks.current_status)
                utils.write_json(stocks.get_overview(logger=logger,market_open=False),OUTPUT_DIR_OVERVIEW,logger=logger)
                utils.write_config(stocks,ENDING_CONFIG_PATH,logger=logger)
                sh.copy(ENDING_CONFIG_PATH,"./latest_state.json")
                break
        else:
            scraper=YahooScraper()
            if scraper.all_markets_closed(stocks.bought_stocks,logger) or ("STOPALGORITHM" in commands['commands']):
                logger.info("Terminating algorithm because all relevant markets are closed or it was instructed by the user",extra={'function':FUNCTION})
                stocks.bought_stocks=utils.close_markets(stocks.current_status)
                utils.write_json(stocks.get_overview(logger=logger,market_open=False),OUTPUT_DIR_OVERVIEW,logger=logger)
                utils.write_config(stocks,ENDING_CONFIG_PATH,logger=logger)
                sh.copy(ENDING_CONFIG_PATH,"./latest_state.json")
                break

    return True



start_algorithm(fixed_rounds=1)
#start_algorithm(fixed_rounds=2,config_file="./latest_state.json")







