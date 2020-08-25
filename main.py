from flask import Flask,send_from_directory,jsonify,make_response
from flask_restful import Api,Resource,abort,reqparse
import threading
import utils
import os.path
import json
import time

from main_algo import start_algorithm

OUTPUT_DIR="./output/"
OUTPUT_DIR_COMMANDS=OUTPUT_DIR+"ALGO_COMMANDS_LOG_{}.txt".format(utils.date_now_filename())

commands_parser=reqparse.RequestParser()
commands_parser.add_argument("tickers",type=str,help="Ticker of which you want to sell all currently owned stocks.")
commands_parser.add_argument("commands",type=str,help="General commands you want to pass.")

config_parser=reqparse.RequestParser()
config_parser.add_argument("main",type=str,help="Post a new config value for main. Example: str(seconds_to_sleep:30).")
config_parser.add_argument("trade_logic",type=str,help="Post a new config value for trade_logic. Example: str(seconds_to_sleep:30).")
config_parser.add_argument("logging",type=str,help="Post a new config value for logging. Example: str(seconds_to_sleep:30).")


global start_time
start_time=time.time()

class Plot(Resource):
    def get(self,ticker):
        plotpath=utils.get_plot(ticker)
        if plotpath==None:
            abort(404,message="Plot for {} does not exist.".format(ticker.upper()))
        filename=os.path.basename(plotpath)
        return send_from_directory("/Users/glennviroux/Documents/VSCode/algoTrading/output/plots/",filename,attachment_filename=filename)

class Retrieve(Resource):
    def get(self,data_id):
        datapath=utils.get_latest_log(data_id.upper())
        if datapath==None:
            abort(404,message="Datapath for {} does not exist.".format(data_id))
        dirname=os.path.dirname(datapath)
        filename=os.path.basename(datapath)
        return send_from_directory(dirname,filename,attachment_filename=filename)

class GetInfo(Resource):
    def get(self,info_id):
        if info_id.upper()=="ALGOSTATUS":
            isrunning="No"
            duration="0"
            for thread in threading.enumerate():
                if thread.getName()=="main_algo":
                    isrunning="Yes"
                    duration=str(time.time()-start_time)
            return make_response(jsonify(isrunning=isrunning,duration=duration),200)

        abort(404,message="This operation is not allowed.")

class ConfigCommands(Resource):
    config_file="./config/config.json"

    def get(self):
        config_data=utils.read_json_data(self.config_file)
        if not config_data:
            abort(404,message="No valid config file found.")
        
        dirname=os.path.dirname(self.config_file)
        filename=os.path.basename(self.config_file)
        return send_from_directory(dirname,filename,attachment_filename=filename)

    def post(self):
        config_data=utils.read_json_data(self.config_file)
        if not config_data:
            abort(404,message="No valid config file found.")

        args=config_parser.parse_args()
        args_dict=dict(args)

        for key in args_dict:
            if not args_dict[key]:
                continue

            if not key in config_data:
                abort(404,message="Category {} is not valid.".format(key))

            pair=args_dict[key].split(':')
            if not len(pair)==2:
                abort(404,message="No valid config value provided. Format is str(parameter:value).")
            
            config_data[key][pair[0]]=pair[1]

        utils.write_json(config_data,self.config_file)

        return config_data,200


class Commands(Resource):
    def post(self):
        global start_time
        commands_log=utils.get_latest_log("COMMANDS")
        if not commands_log:
            utils.initialize_json_file(OUTPUT_DIR_COMMANDS)
            commands_log=OUTPUT_DIR_COMMANDS
        existing_data=utils.read_json_data(commands_log)
        tickers=[]
        commands=[]
        if existing_data:
            if len(existing_data['tickers'])>0:
                tickers=existing_data['tickers']

            if len(existing_data['commands'])>0:
                commands=existing_data['commands']

        args=commands_parser.parse_args()

        args_dict=dict(args)
        tickers.append(args_dict['tickers'])
        commands.append(args_dict['commands'])
        if "SELLALL" in commands:
            tickers.append("ALLSTOCKS")

        if "CLEANSTARTALGORITHM" in commands:
            for thread in threading.enumerate():
                if thread.getName()=="main_algo":
                    abort(404,message="Algorithm is already running.")

            algo_thread=threading.Thread(target=start_algorithm,name="main_algo")            
            start_time=time.time()
            algo_thread.start()
            commands.remove("CLEANSTARTALGORITHM")

        if "STARTALGORITHMFROMLATEST" in commands:
            for thread in threading.enumerate():
                if thread.getName()=="main_algo":
                    abort(404,message="Algorithm is already running.")

            algo_thread=threading.Thread(target=start_algorithm,name="main_algo",kwargs={'initial_state_file':'./config/latest_state.json'})
            start_time=time.time()
            algo_thread.start()
            commands.remove("STARTALGORITHMFROMLATEST")

        if "STOPALGORITHM" in commands:
            algo_running=False
            for thread in threading.enumerate():
                if thread.getName()=="main_algo":
                    algo_running=True
            if not algo_running:
                abort(404,message="Algorithm isn't running at this moment.")

        tickers=[ticker for ticker in tickers if ticker]
        commands=[command for command in commands if command]

        result={'tickers':list(set(tickers)),'commands':list(set(commands))}
        utils.write_json(result,OUTPUT_DIR_COMMANDS)
        return result,200


def start_server():
    app=Flask(__name__)
    api=Api(app)

    api.add_resource(Commands,"/commands/")
    api.add_resource(Plot,"/plots/<string:ticker>")
    api.add_resource(Retrieve,"/retrieve/<string:data_id>")
    api.add_resource(GetInfo,"/info/<string:info_id>")
    api.add_resource(ConfigCommands,"/config/")

    app.run(debug=True,host='192.168.0.21',port=5050)

if __name__ == "__main__":
    start_server()
