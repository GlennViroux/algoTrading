#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import datetime
from pytz import timezone
import pandas as pd
import glob
import os,os.path
import shutil
import errno
import json

### LOG WRITING OPERATIONS ###
def date_now():
    return datetime.now().strftime("%Y/%m/%d-%H:%M:%S")

def date_now_filename():
    return datetime.now().strftime("%Y%m%d%H%M%S")

def date_now_flutter():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def write_stocks(current_stocks):
    '''
    This function pretty prints the list of currently owned stocks.
    '''
    l=[]
    if isinstance(current_stocks,dict):
        l=list(current_stocks.keys())
    elif isinstance(current_stocks,list):
        l=current_stocks
    
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
            print(exc)
            raise

def safe_open(path,option):
    '''
    This function opens "path" for writing, creating directories if needed.
    '''
    mkdir_p(os.path.dirname(path))
    return open(path,option)

### WRITE DATA FOR API ###
def write_json(data,path):
    '''
    This function writes the data (in dictionary format) in JSON format.
    '''
    try:
        with safe_open(path,"w") as f:
            f.write(json.dumps(data,indent=2))
    except:
        print("Failed to safely open the JSON file, nothing was written.\n")

def write_plotdata(bought_stocks_data,path):
    '''
    This function writes the current plotdata in JSON format.
    '''
    df=pd.DataFrame(bought_stocks_data)
    result={}
    for ticker in pd.unique(df.ticker):
        df_ticker=df[df['ticker']==ticker]
        result[ticker]={}
        for timestamp in df_ticker.timestamps:
            df_timestamp=df[(df['ticker']==ticker) & (df['timestamps']==timestamp)]
            new_dict = {'bid':str(df_timestamp.bid.iloc[0]),
                        'ask':str(df_timestamp.ask.iloc[0]),
                        'bought':str(df_timestamp.bought.iloc[0]),
                        'EMA_small':str(df_timestamp.EMA_small.iloc[0]),
                        'EMA_big':str(df_timestamp.EMA_big.iloc[0])}

            result[ticker][str(timestamp)]=new_dict

    try:
        with safe_open(path,"w") as f:
            f.write(json.dumps(result,indent=2))
    except:
        print("Failed to safely open the output plotdata file, nothing was written.\n")
        
def write_config(stocks,path):
    '''
    This function writes the ending config of the daily execution.
    '''
    result={}
    d=stocks.bought_stock_data
    d['timestamps']=[str(t) for t in stocks.bought_stock_data['timestamps']]

    result["balance"]=stocks.balance
    result["current_stocks"]=stocks.current_stocks
    result["previously_checked_stocks"]=stocks.previously_checked_stocks
    result["bought_stock_data"]=d
    result["current_status"]=stocks.current_status
    result["tosell"]=stocks.tosell

    try:
        with safe_open(path,"w") as f:
            f.write(json.dumps(result,indent=2))
    except:
        print("Failed to safely open the output config file, nothing was written.\n")



### RETRIEVE/READ DATA AND FILES ###
def get_latest_log(keyword):
    list_of_files=glob.glob('./output/ALGO_{}_LOG*'.format(keyword))
    if not list_of_files:
        return None
    return max(list_of_files, key=os.path.getctime)

def get_plot(ticker):
    list_of_files=glob.glob('./output/plots/*{}.png'.format(ticker.upper()))
    if not list_of_files:
        return None
    return max(list_of_files, key=os.path.getctime)

def read_json_data(log):
    if not log:
        return {}
    try:
        with safe_open(log,"r") as f:
            data=f.read()
        return json.loads(data)
    except:
        print("Failed to safely open the log.")

def read_commands(log):
    commands=read_json_data(log)
    if not 'tickers' in commands:
        commands['tickers']=[]
    if not 'commands' in commands:
        commands['commands']=[]
    return commands


def read_initial_values(config_path):
    try:
        with safe_open(config_path,"r") as f:
            data=f.read()
        json_data=json.loads(data)
        return json_data
    except:
        print("Failed to safely open the config file.")


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


### TIME OPERATIONS ###
