#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import logging.config
import urllib.request as request
from contextlib import closing
from datetime import datetime,timedelta
import pandas_market_calendars as mcal
from pytz import timezone
import pandas as pd
import glob
import os,os.path
import shutil
import errno
import json
import pytz
from yahoo_api import YahooAPI

### LOG WRITING OPERATIONS ###
def date_now():
    return datetime.now().strftime("%Y/%m/%d-%H:%M:%S")

def date_now_filename():
    return datetime.now().strftime("%Y%m%d%H%M%S")

def date_now_flutter():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def write_stocks(bought_stocks):
    '''
    This function pretty prints the list of currently owned stocks.
    '''
    l=[]
    if isinstance(bought_stocks,dict):
        l=list(bought_stocks.keys())
    elif isinstance(bought_stocks,list):
        l=bought_stocks
    
    result=""
    for stock in l:
        result+=stock+";"
    return result

def write_output(line,path):
    '''
    This files writes a new line to the output file (log).
    '''
    try:
        with safe_open(path,"a") as f:
            f.write(line+'\n')
    except:
        f.write("Failed to safely open the output log file, nothing was written.\n")

def safe_write(data,path,option):
    '''
    This files writes a new line to the output file (log).
    '''
    try:
        with safe_open(path,option) as f:
            f.write(data)
    except:
        print("UTILS: SAFE WRITE ERROR")
        pass

def write_output_formatted(mode,text,path):
    '''
    This files writes a new, formatted line to the output file (log).
    '''
    try:
        with safe_open(path,"a") as f:
            f.write("{} -:- {:22} {}".format(date_now(),mode,text)+'\n')
    except:
        print("Failed to safely open the output log file, nothing was written.\n")


### YAHOO PARSING OPERATION ###
def yahoo_float(string):
    '''
    This function reads a yahoo value and returns a float.
    '''
    if ("," in string) and ("." in string):
        return float(string.replace(',',''))
    else:
        return float(string)


### DIRECTORY OPERATIONS ###
def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno==errno.EEXIST or os.path.isdir(path):
            pass
        else:
            raise

def safe_open(path,option):
    '''
    This function opens "path" for writing, creating directories if needed.
    '''
    mkdir_p(os.path.dirname(path))
    return open(path,option)

def safe_copy(source,dest):
    '''
    Safe copy of file
    '''
    mkdir_p(os.path.dirname(dest))
    shutil.copyfile(source,dest)


### WRITE DATA FOR API ###
def write_json(data,path,logger=None):
    FUNCTION='write_json'
    '''
    This function writes the data (in dictionary format) in JSON format.
    '''
    if path:
        try:
            with safe_open(path,"w") as f:
                f.write(json.dumps(data,indent=2))
        except:
            if logger:
                logger.debug("Unable to write json data. Exception occured.",extra={'function':FUNCTION},exc_info=True)

def write_plotdata(monitored_stock_data,path,logger):
    FUNCTION='write_plotdata'
    '''
    This function writes the current plotdata in JSON format.
    {
        'ticker1':
        {
            'timestamp1':
            {
                'close':...,
                'smallEMA':...,
                'bigEMA':...
            },
            'timestamp2':
            {
                'close':...,
                'smallEMA':...,
                'bigEMA':...
            }
        },
        'ticker2': {...}
    }
    '''
    result={}
    for ticker in monitored_stock_data:
        result[ticker]={}
        timestamps=monitored_stock_data[ticker]['timestamps']
        for i in range(len(timestamps)):
            new_dict={
                'close':str(monitored_stock_data[ticker]['close'][i]),
                'smallEMA':str(monitored_stock_data[ticker]['smallEMA'][i]),
                'bigEMA':str(monitored_stock_data[ticker]['bigEMA'][i]),
            }
            result[ticker][str(timestamps[i])]=new_dict

    try:
        with safe_open(path,"w") as f:
            f.write(json.dumps(result,indent=2))
    except:
        logger.debug("Unable to write plotdata. Exception occured.",extra={'function':FUNCTION},exc_info=True)
        
def write_state(stocks,path,logger):
    FUNCTION='write_state'
    '''
    This function writes the ending config of the daily execution.
    '''
    result={}
    d=stocks.monitored_stock_data
    for ticker in d:
        d[ticker]['timestamps']=[str(t) for t in stocks.monitored_stock_data[ticker]['timestamps']]

    result["balance"]=stocks.balance
    result["bought_stocks"]=stocks.bought_stocks
    result["monitored_stocks"]=stocks.monitored_stocks
    result["monitored_stock_data"]=d
    result["archive"]=stocks.archive
    result["current_status"]=stocks.current_status
    result["interesting_stocks"]=stocks.interesting_stocks
    result["not_interesting_stocks"]=stocks.not_interesting_stocks
    result["yahoo_calls"]=stocks.yahoo_calls

    try:
        with safe_open(path,"w") as f:
            f.write(json.dumps(result,indent=2))
    except:
        logger.debug("Unable to write config. Exception occured.",extra={'function':FUNCTION},exc_info=True)

def write_log_json(algolog_path,output_path,logger=None):
    FUNCTION='write_log_json'
    '''
    Write log data in JSON format
    '''
    result=[]
    try:
        with safe_open(algolog_path,"r") as f:
            for line in f:
                elems=[elem.replace("]","").replace("[","").strip() for elem in line.split(" - ")]
                new_elem = {
                    "Timestamp":elems[0],
                    "Category":elems[1],
                    "Function":elems[2],
                    "Info":elems[3]
                }
                result.append(new_elem)

        with safe_open(output_path,"w") as f:
            f.write(json.dumps(result))
    except:
        if logger:
            logger.debug("Unable to read json data. Exception occured.",extra={'function':FUNCTION},exc_info=True)
            return []

def archive_session(filelist,logger):
    FUNCTION='archive_session'
    '''
    Archive the file with all transactions according to its start date.
    '''

    for myfile in filelist:
        if not os.path.isfile(myfile):
            logger.error("File: {} doesn't exist.".format(myfile),extra={'function':FUNCTION})
            return None

        filename=os.path.basename(myfile)

        filename_stripped=filename.split(".")[0]

        filename_date=filename_stripped.split("_")[-1]
        year=filename_date[:4]
        month=filename_date[4:6]
        day=filename_date[6:8]
        hour=filename_date[8:10]
        minute=filename_date[10:12]
        second=filename_date[12:14]

        destination="./past_sessions/"+year+"/"+month+"/"+day+"/"+hour+"/"+minute+"/"+second+"/"+filename

        safe_copy(myfile,destination)

### RETRIEVE/READ DATA AND FILES ###
def get_latest_log(keyword,basepath="./output/",logger=None):
    FUNCTION='get_latest_log'
    list_of_files=glob.glob(basepath+'ALGO_{}_LOG*'.format(keyword))
    if not list_of_files:
        if logger:
            logger.debug("No file found for keyword {}".format(keyword),extra={'function':FUNCTION})
        return None
    return max(list_of_files, key=os.path.getctime)

def get_plot(ticker):
    list_of_files=glob.glob('./output/plots/*{}.png'.format(ticker.upper()))
    if not list_of_files:
        return None
    return max(list_of_files, key=os.path.getctime)

def read_config(config_file,logger=None):
    #FUNCTION='read_config'
    json_data=read_json_data(config_file,logger=logger)
    result={}
    result['main']={}
    result['trade_logic']={}
    result['logging']={}

    result['main']['seconds_to_sleep']=int(json_data['main']["seconds_to_sleep"])
    result['main']['plot_data']=(json_data['main']['plot_data']=="true")
    result['main']['ignore_market_hours']=(json_data['main']['ignore_market_hours']=="true")
    result['main']['include_pre_trading']=(json_data['main']['include_pre_trading']=="true")
    result['main']['include_post_trading']=(json_data['main']['include_post_trading']=="true")
    result['main']['sell_all_before_finish']=(json_data['main']['sell_all_before_finish']=="true")
    result['main']['initial_number_of_stocks']=int(json_data['main']['initial_number_of_stocks'])
    result['main']['check_for_new_stocks']=(json_data['main']['check_for_new_stocks']=="true")

    result['trade_logic']['money_to_spend']=float(json_data['trade_logic']['money_to_spend'])
    result['trade_logic']['yahoo_latency_threshold']=float(json_data['trade_logic']['yahoo_latency_threshold'])
    result['trade_logic']['yahoo_interval']=json_data['trade_logic']['yahoo_interval']
    result['trade_logic']['yahoo_period_small_EMA']=int(json_data['trade_logic']['yahoo_period_small_EMA'])
    result['trade_logic']['yahoo_period_big_EMA']=int(json_data['trade_logic']['yahoo_period_big_EMA'])
    result['trade_logic']['yahoo_period_historic_data']=int(json_data['trade_logic']['yahoo_period_historic_data'])
    result['trade_logic']['number_of_big_EMAs_threshold']=int(json_data['trade_logic']['number_of_big_EMAs_threshold'])
    result['trade_logic']['big_EMA_derivative_threshold']=float(json_data['trade_logic']['big_EMA_derivative_threshold'])
    result['trade_logic']['surface_indicator_threshold']=float(json_data['trade_logic']['surface_indicator_threshold'])
    result['trade_logic']['EMA_surface_plus_threshold']=float(json_data['trade_logic']['EMA_surface_plus_threshold'])
    result['trade_logic']['EMA_surface_min_threshold']=float(json_data['trade_logic']['EMA_surface_min_threshold'])
    result['trade_logic']['number_of_EMA_crossings']=int(json_data['trade_logic']['number_of_EMA_crossings'])

    result['logging']['level_console']=json_data['logging']['level_console']
    result['logging']['level_file']=json_data['logging']['level_file']

    return result

def read_json_data(file_path,logger=None):
    FUNCTION='read_json_data'
    if not file_path:
        logger.debug("No file found.",extra={'function':FUNCTION})
        return {}
    try:
        with safe_open(file_path,"r") as f:
            data=f.read()
        return json.loads(data)
    except:
        if logger:
            logger.debug("Unable to read json data. Exception occured.",extra={'function':FUNCTION},exc_info=True)
            return {}
        else:
            print("Unable to read json data. Exception occured.")
            return {}

def read_commands(log,logger=None):
    commands=read_json_data(log,logger)
    if not 'tickers' in commands:
        commands['tickers']=[]
    if not 'commands' in commands:
        commands['commands']=[]
    return commands

def initialize_commands_file(file_path,logger=None):
    #FUNCTION='initialize_commands_file'
    with safe_open(file_path,"w") as f:
        data={
            'tickers_to_sell':[],
            'tickers_to_buy':[],
            'commands':[]
        }
        f.write(json.dumps(data,indent=2))

def get_dates_past_sessions():
    '''
    Get dates of the past sessions in flutter format
    '''
    result=[]
    for t in os.walk("./past_sessions/"):
        if t[1] or not t[2]:
            continue

        elems=t[0].split("/")
        second=elems[-1]
        minute=elems[-2]
        hour=elems[-3]
        day=elems[-4]
        month=elems[-5]
        year=elems[-6]

        date=year+"-"+month+"-"+day+" "+hour+":"+minute+":"+second
        result.append(date)

    return result

def get_past_session_file(data_id,date,logger=None):
    FUNCTION='get_past_session_file'
    '''
    Get transactions done in a previous session at a specific date.
    '''
    if not len(date)==19:
        if logger:
            logger.error("Provided date: {} is not in a valid format.".format(date),extra={'function':FUNCTION})
        return False

    year=date[:4]
    month=date[5:7]
    day=date[8:10]
    hour=date[11:13]
    minute=date[14:16]
    second=date[17:19]

    path="./past_sessions/"+year+"/"+month+"/"+day+"/"+hour+"/"+minute+"/"+second+"/"

    return get_latest_log(data_id,basepath=path,logger=logger)


### PYTHON SOCKET PROGRAMMING ###
def receive_chunks(conn,size):
    chunks=[]
    bytes_recvd=0
    while bytes_recvd<size:
        chunk = conn.recv(min(size-bytes_recvd,2048))
        if chunk==b'':
            raise RuntimeError("Socket connection broken")
        chunks.append(chunk)
        bytes_recvd+=len(chunk)
    return b''.join(chunks)

def send_chunks(conn,data):
    totalsent=0
    size=len(data)
    while totalsent<size:
        sent=conn.send(data[totalsent:])
        if sent==0:
            raise RuntimeError("Socket connection broken.")
        totalsent+=sent   


### HOUSEKEEPING ###
def clean_output(output_dir,output_dir_plots):
    '''
    This function cleans the output directory (log+output plots).
    '''
    if not os.path.isdir(output_dir):
        mkdir_p(output_dir)

    for filename in os.listdir(output_dir):
        file_path = os.path.join(output_dir, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))

    mkdir_p(output_dir_plots)

def clean_previous_sessions(output_dir_prev_sessions="./past_sessions"):
    '''
    This function cleans the output directory (log+output plots).
    '''
    if not os.path.isdir(output_dir_prev_sessions):
        mkdir_p(output_dir_prev_sessions)

    for filename in os.listdir(output_dir_prev_sessions):
        file_path = os.path.join(output_dir_prev_sessions, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))


### TRADE OPERATIONS ###
def close_markets(current_status):
    '''
    This function updates all the current statuses of the stocks by closing the markets.
    '''
    new_status=current_status
    for stock in current_status:
        new_status[stock]['market_state']="CLOSED"

    return new_status

def get_deriv_surf(input,logger):
    FUNCTION="get_deriv_surf"
    '''
    Mathematical operations in order to characterize a stock.
    '''
    input_list=list(input.dropna())

    if not input_list:
        logger.debug("An empty or no valid input list is provided",extra={'function':FUNCTION})
        return None

    Ay=input_list[0]
    By=input_list[-1]
    Ax=0
    Bx=len(input_list)

    D=(By-Ay)/(Bx-Ax)

    y = lambda x : D*(x-Ax)+Ay

    A=0
    for i in range(len(input_list)):
        A+=abs(y(i)-input_list[i])
    
    avg=(Ay+By)/2
    A_result=A/avg

    logger.debug("Bx-Ax={}, By-Ay={}, D={}, A={}, A_result={}".format(Bx-Ax,By-Ay,D,A,A_result),extra={'function':FUNCTION})

    return D,A_result

def calculate_surfaces_EMAs(smallEMAs,bigEMAs,logger):
    FUNCTION='calculate_surfaces_EMAs'
    '''
    Mathematical operations in order to characterize a stock.
    Aplus : bigEMA higher than smallEMA
    Amin : bigEMA smaller than smallEMA
    '''
    bigEMA_list=list(bigEMAs.dropna())
    smallEMA_list=list(smallEMAs.dropna())

    if not len(bigEMA_list)==len(smallEMA_list):
        if logger:
            logger.debug("Length of available big EMAs ({}) is not equal to length of small EMAs ({})".format(len(bigEMA_list),len(smallEMA_list)),extra={'function':FUNCTION})
        return None

    Aplus=0
    Amin=0
    for i in range(len(bigEMA_list)):
        diff=bigEMA_list[i]-smallEMA_list[i]
        if diff>=0:
            Aplus+=diff
        else:
            Amin+=diff
    
    return Aplus,Amin

def get_number_of_crossings(smallEMAs,bigEMAs,logger):
    FUNCTION='get_number_of_crossings'
    '''
    Mathematical operations in order to characterize a stock.
    Aplus : bigEMA higher than smallEMA
    Amin : bigEMA smaller than smallEMA
    '''
    bigEMA_list=list(bigEMAs.dropna())
    smallEMA_list=list(smallEMAs.dropna())

    if not len(bigEMA_list)==len(smallEMA_list):
        if logger:
            logger.debug("Length of available big EMAs ({}) is not equal to length of small EMAs ({})".format(len(bigEMA_list),len(smallEMA_list)),extra={'function':FUNCTION})
        return None

    result=0
    # 1 when bigEMA>=smallEMA
    # 0 when bigEMA<smallEMA
    cond=(bigEMA_list[0]>=smallEMA_list[0])
    i=1
    while i<len(bigEMA_list):
        new_cond=(bigEMA_list[i]>=smallEMA_list[i])
        if not new_cond==cond:
            cond=new_cond
            result+=1
            i+=10
        else:
            i+=1

    logger.debug("Number of EMA crossings: {}".format(result),extra={'function':FUNCTION})

    return result

def get_start_business_date(exchange,input_days_in_past,logger=None):
    FUNCTION='get_start_business_date'
    '''
    Get start business date
    '''
    try:
        cal=mcal.get_calendar(exchange)
    except RuntimeError:
        if logger:
            logger.error("Exchange {} is not recognized by pandas market calendar.".format(exchange),extra={'function':FUNCTION})
        return None

    start=datetime.strftime(datetime.now()-timedelta(days=100),"%Y-%m-%d")
    end=datetime.strftime(datetime.now(),"%Y-%m-%d")

    series=cal.valid_days(start_date=start, end_date=end)

    return series[-input_days_in_past]

def configure_logger(name,output_log,config_params):
    logging.config.dictConfig({
        'version':1,
        'formatters': {
            'default': {
                'format': "[%(asctime)s] - [%(levelname)-8s] - [%(function)-30s] - %(message)s", 
                'datefmt': "%Y/%m/%d-%H:%M:%S"
            }
        },
        'handlers':{
            'console': {
                'level':config_params['level_console'],
                'class':'logging.StreamHandler',
                'formatter':'default',
                'stream': 'ext://sys.stdout'
            },
            'file':{
                'level':config_params['level_file'],
                'class':'logging.FileHandler',
                'formatter':'default',
                'filename':output_log
            }
        },
        'loggers':{
            'default':{
                'level':'DEBUG',
                'handlers':['console','file']
            }
        },
        'disable_existing_loggers': False
    })
    return logging.getLogger(name)

def before_close(period=20):
    '''
    Returns true if now is period minutes or closer to the closing of the market.
    '''
    now=datetime.now()

    close=datetime(year=now.year,month=now.month,day=now.day,hour=22,minute=0,second=0,microsecond=0)

    return now>=close-timedelta(minutes=period)