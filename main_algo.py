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
OUTPUT_DIR_ARCHIVE=OUTPUT_DIR+"ALGO_ARCHIVE_LOG_{}.txt".format(utils.date_now_filename())
OUTPUT_DIR_PLOTDATA=OUTPUT_DIR+"ALGO_PLOTDATA_LOG_{}.txt".format(utils.date_now_filename())
OUTPUT_DIR_OVERVIEW=OUTPUT_DIR+"ALGO_OVERVIEW_LOG_{}.txt".format(utils.date_now_filename())
ENDING_STATE_PATH=OUTPUT_DIR+"ALGO_ENDING_STATE_{}.txt".format(utils.date_now_filename())

# Parse input arguments
parser=argparse.ArgumentParser(description="GLENNY's argument parser")
parser.add_argument('--initial_state_file','-i',type=str,help='File in JSON format containing initial state.',default="./config/initial_state.json")
parser.add_argument('--config_file','-c',type=str,help='Configuration file containing algorithm parameters.',default="./config/config.json")
args=parser.parse_args()

def update_state(stocks,logger):
    FUNCTION='write_last_state'
    '''
    Write the current state to the latest_state json file.
    '''
    # Initialize yahoo_calls if not done already
    stocks.update_yahoo_calls(add_call=False,logger=logger)

    # Write current overview
    logger.debug("Writing overview...",extra={'function':FUNCTION})
    utils.write_json(stocks.get_overview(logger=logger),OUTPUT_DIR_OVERVIEW,logger=logger)
    logger.debug("Written overview...",extra={'function':FUNCTION})

    # Write current status per monitored stock
    logger.debug("Writing current status...",extra={'function':FUNCTION})
    utils.write_json(stocks.current_status,OUTPUT_DIR_STATUS,logger=logger)
    logger.debug("Written current status",extra={'function':FUNCTION})

    # Write archive data
    logger.debug("Writing current archives...",extra={'function':FUNCTION})
    d={'data':stocks.archive}
    utils.write_json(d,OUTPUT_DIR_ARCHIVE,logger=logger)
    logger.debug("Written current archives",extra={'function':FUNCTION})

    # Write plotdata for all monitored stocks
    logger.debug("Writing plotdata...",extra={'function':FUNCTION})
    utils.write_plotdata(stocks.monitored_stock_data,OUTPUT_DIR_PLOTDATA,logger=logger)
    logger.debug("Written plotdata",extra={'function':FUNCTION})

    # Write ending state and copy to config folder
    logger.debug("Writing and copying ending state...",extra={'function':FUNCTION})
    utils.write_state(stocks,ENDING_STATE_PATH,logger=logger)
    sh.copy(ENDING_STATE_PATH,"./config/latest_state.json")
    logger.debug("Written and copied ending state",extra={'function':FUNCTION})


def start_algorithm(initial_state_file=None,config_file=None,fixed_rounds=None):
    FUNCTION='main'
    # Clean output directory
    utils.clean_output(OUTPUT_DIR,OUTPUT_DIR_PLOTS)

    # Get config params
    if not config_file:
        config_file=args.config_file
    config_params=utils.read_config(config_file)

    # Configure logging
    logger=utils.configure_logger("default",OUTPUT_DIR_LOG,config_params["logging"])

    logger.debug("Starting algorithm.",extra={'function':FUNCTION})

    # Initialize stocks object with configuration values
    if not initial_state_file:
        initial_state_file=args.initial_state_file

    logger.debug("Reading initial values from config file: {}...".format(initial_state_file),extra={'function':FUNCTION})
    init_val=utils.read_json_data(initial_state_file,logger=logger)
    logger.debug("Read initial values from config file: {}".format(initial_state_file),extra={'function':FUNCTION})

    stocks=Stocks(balance=init_val["balance"],
                    bought_stocks=init_val["bought_stocks"],
                    monitored_stocks=init_val["monitored_stocks"],
                    current_status=init_val["current_status"],
                    monitored_stock_data=init_val["monitored_stock_data"],
                    archive=init_val["archive"],
                    interesting_stocks=init_val["interesting_stocks"],
                    not_interesting_stocks=init_val["not_interesting_stocks"],
                    yahoo_calls=init_val["yahoo_calls"])

    # Initialize status files
    update_state(stocks,logger)

    # Check which stocks to monitor
    logger.debug("Getting and initializing list of stocks to monitor...",extra={'function':FUNCTION})
    stocks.initialize_stocks(logger=logger,config_params=config_params,update_nasdaq_file=False)
    logger.debug("Got and initialized stocks to monitor.",extra={'function':FUNCTION})

    # Set initial values
    stock_market_open=True
    counter=0

    while stock_market_open:
        # Update config params
        if not config_file:
            config_file=args.config_file
        config_params=utils.read_config(config_file)

        # Read and save whether the user has ordered manually to sell a certain stock, and if true, sell it
        commands_log=utils.get_latest_log("COMMANDS",logger=logger)
        commands={'commands':[],'tickers':[]}
        if commands_log:
            commands=utils.read_commands(commands_log,logger=logger)
            stocks.hard_sell_check(commands,commands_log,config_params,logger=logger)

        # Loop through monitored stocks
        logger.debug("Checking monitored stocks...",extra={'function':FUNCTION})
        for stock in stocks.monitored_stocks:
            stocks.check_monitored_stock(stock,config_params=config_params,logger=logger)
        logger.debug("Checked all monitored stocks",extra={'function':FUNCTION})

        # Check if we should monitor more stocks
        logger.debug("Checking if we should monitor more stocks...",extra={'function':FUNCTION})
        stocks.check_to_monitor_new_stocks(config_params,logger)
        logger.debug("Checked if we should monitor more stocks",extra={'function':FUNCTION})


        # Plot data per monitored stock
        if config_params['main']['plot_data']:
            logger.debug("Plotting monitored stock data...",extra={'function':FUNCTION})
            stocks.plot_monitored_stock_data(OUTPUT_DIR_PLOTS,logger=logger)
            logger.debug("Plotted all monitored stock data...",extra={'function':FUNCTION})

        # Check if all markets are closed
        if fixed_rounds:
            counter+=1
            if counter>=fixed_rounds:
                logger.debug("Terminating algorithm because of configured fixed rounds",extra={'function':FUNCTION})
                stocks.current_status=utils.close_markets(stocks.current_status)
                update_state(stocks,logger)
                break
        else:
            scraper=YahooScraper()
            if (scraper.all_markets_closed(stocks.monitored_stocks,logger) and not config_params['main']['ignore_market_hours']) or ("STOPALGORITHM" in commands['commands']):
                if "STOPALGORITHM" in commands['commands']:
                    commands['commands'].remove("STOPALGORITHM")
                utils.write_json(commands,commands_log,logger=logger)
                logger.info("Terminating algorithm because all relevant markets are closed or it was instructed by the user",extra={'function':FUNCTION})
                stocks.current_status=utils.close_markets(stocks.current_status)
                update_state(stocks,logger)
                break

        # Update state
        update_state(stocks,logger)
        
        # Sleep 
        seconds_to_sleep=config_params['main']['seconds_to_sleep']
        logger.info("Sleeping {} seconds".format(seconds_to_sleep),extra={'function':FUNCTION})
        time.sleep(seconds_to_sleep)

    return True


#start_algorithm(fixed_rounds=3)







