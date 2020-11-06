from flask import Flask,send_from_directory,jsonify,make_response
from flask_restful import Api,Resource,abort,reqparse
from pathlib import Path
import threading
import utils
import os.path
import json
import time

from main_algo import start_algorithm
from launch_backtesting import main as main_backtesting

OUTPUT_DIR="./output/"

commands_parser=reqparse.RequestParser()
commands_parser.add_argument("tickers_to_sell",type=str,help="Ticker of which you want to sell all currently owned stocks.")
commands_parser.add_argument("tickers_to_stop_monitor",type=str,help="Tickers you wish to stop monitoring.")
commands_parser.add_argument("commands",type=str,help="General commands you want to pass.")

backtesting_parser=reqparse.RequestParser()
backtesting_parser.add_argument("command",required=True,type=str)
backtesting_parser.add_argument("days",type=int)
backtesting_parser.add_argument("number",type=int)
backtesting_parser.add_argument("sell_criterium",type=str,choices=('EMA','price'))


config_parser=reqparse.RequestParser()
config_parser.add_argument("main",type=str,help="Post a new config value for main. Example: str(seconds_to_sleep:30).")
config_parser.add_argument("trade_logic",type=str,help="Post a new config value for trade_logic. Example: str(seconds_to_sleep:30).")
config_parser.add_argument("logging",type=str,help="Post a new config value for logging. Example: str(seconds_to_sleep:30).")


global start_time
start_time=time.time()

class BackTesting(Resource):
    def get(self,ticker):
        if ticker.split("-")[0]=="stats":
            what = ticker.split("-")[1]
            sell_criterium = ticker.split("-")[2]
            param = ticker.split("-")[3]
            plotpath=utils.get_back_stat_plot(param,what,sell_criterium)
            if plotpath==None:
                abort(404,message="Plot for {} does not exist.".format(ticker))
            plotpath = Path(plotpath)
            return send_from_directory(plotpath.parent,plotpath.name,attachment_filename=plotpath.name)


        plotpath=utils.get_back_plot(ticker)
        if plotpath==None:
            abort(404,message="Plot for {} does not exist.".format(ticker.upper()))
        filename=os.path.basename(plotpath)
        return send_from_directory("./backtesting/back_plots/",filename,attachment_filename=filename)

    def post(self):
        msg = 'All good!'
        args=backtesting_parser.parse_args()

        command = args['command']
        if command.lower()=="cleanbacktesting":
            os.system("rm -rf ./backtesting/*plots*")
            os.system("rm ./backtesting/backtesting_stats.csv")
            os.system("touch ./backtesting/backtesting_stats.csv")
            os.system("rm ./backtesting/backtesting_cumulative.csv")
            os.system("touch ./backtesting/backtesting_cumulative.csv")
            from backtesting import BackTesting
            BackTesting.upload_results()
            BackTesting.upload_stats()
        elif command.lower()=="launchbacktesting":
            for thread in threading.enumerate():
                if thread.getName()=='main_backtesting':
                    return "Backtrading algorithm is already running.",420

            days = args['days'] if args['days'] else 42
            number = args['number'] if args['number'] else 1
            sell_criterium = args['sell_criterium'] if args['sell_criterium'] else 'EMA'
            backtesting_thread = threading.Thread(target=main_backtesting,name='main_backtesting',kwargs={'days':days,'number':number,'sell_criterium':sell_criterium})
            backtesting_thread.start()
            return "All good!",200
        elif command.lower()=="refreshbacktesting":
            from backtesting import BackTesting
            BackTesting.upload_results()
            BackTesting.upload_stats()
        else:
            abort(404,message='A not valid command ({}) was provided.'.format(command))

        return msg,200


class Retrieve(Resource):
    def get(self,data_id):
        if data_id=="backtesting":
            if not os.path.isfile("./backtesting/backtesting_cumulative.csv"):
                abort(404,message="No cumulative backtesting CSV exists :(")
            return send_from_directory("./backtesting/","backtesting_cumulative.csv",attachment_filename="backtesting_cumulative.csv")

        datapath=utils.get_latest_log(data_id.upper())
        if datapath==None:
            abort(404,message="Datapath for {} does not exist.".format(data_id))
        dirname=os.path.dirname(datapath)
        filename=os.path.basename(datapath)
        return send_from_directory(dirname,filename,attachment_filename=filename)

class RetrievePastSessions(Resource):
    def get(self,date,data_id):
        datapath=utils.get_past_session_file(data_id.upper(),date)
        if datapath==None:
            abort(404,message="Past session for {} and date {} does not exist.".format(data_id,date))
        dirname=os.path.dirname(datapath)
        filename=os.path.basename(datapath)
        return send_from_directory(dirname,filename,attachment_filename=filename)

class GetInfo(Resource):
    def get(self,info_id):
        if info_id.upper()=="ALGOSTATUS":
            isrunning="No"
            is_backtesting_running="No"
            duration="0"
            for thread in threading.enumerate():
                if thread.getName()=="main_algo":
                    isrunning="Yes"
                    duration=str(time.time()-start_time)
                elif thread.getName()=='main_backtesting':
                    is_backtesting_running="Yes"
            return make_response(jsonify(isrunning=isrunning,duration=duration,is_backtesting_running=is_backtesting_running),200)

        elif info_id.upper()=="PASTSESSIONS":
            past_sessions=utils.get_dates_past_sessions()
            return make_response(jsonify(past_sessions),200)

        elif info_id.upper()=="BACKTESTING":
            yql_calls = utils.read_json_data('./backtesting/calls_yql.json')
            if not yql_calls:
                yql_calls = {'hourly_calls':0,'daily_calls':0,'total_calls':0,'duration':0}
            return make_response(jsonify(hourly_calls=yql_calls['hourly_calls'],daily_calls=yql_calls['daily_calls'],total_calls=yql_calls['total_calls'],duration=yql_calls['duration']),200)



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
            OUTPUT_DIR_COMMANDS=OUTPUT_DIR+"ALGO_COMMANDS_LOG_{}.txt".format(utils.date_now_filename())
            utils.initialize_commands_file(OUTPUT_DIR_COMMANDS)
            commands_log=OUTPUT_DIR_COMMANDS
        existing_data=utils.read_json_data(commands_log)
        tickers_to_sell=[]
        tickers_to_stop_monitor=[]
        commands=[]
        if existing_data:
            if 'tickers_to_sell' in existing_data and len(existing_data['tickers_to_sell'])>0:
                tickers_to_sell=existing_data['tickers_to_sell']

            if 'tickers_to_stop_monitor' in existing_data and len(existing_data['tickers_to_stop_monitor'])>0:
                tickers_to_stop_monitor=existing_data['tickers_to_stop_monitor']

            if 'commands' in existing_data and len(existing_data['commands'])>0:
                commands=existing_data['commands']

        args=commands_parser.parse_args()

        args_dict=dict(args)
        if 'tickers_to_sell' in args_dict:
            tickers_to_sell.append(args_dict['tickers_to_sell'])
        if 'tickers_to_stop_monitor' in args_dict:
            tickers_to_stop_monitor.append(args_dict['tickers_to_stop_monitor'])
        if 'commands' in args_dict:
            commands.append(args_dict['commands'])

        if "SELLALL" in commands:
            tickers_to_sell.append("ALLSTOCKS")

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

            algo_thread=threading.Thread(target=start_algorithm,name="main_algo",kwargs={'initial_state_file':'./config/latest_state.json','start_clean':'False'})
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

        if "CLEAN_PREVIOUS_SESSIONS" in commands:
            utils.clean_previous_sessions("./past_sessions/")
            commands.remove("CLEAN_PREVIOUS_SESSIONS")

        tickers_to_sell=[ticker for ticker in tickers_to_sell if ticker]
        tickers_to_stop_monitor=[ticker for ticker in tickers_to_stop_monitor if ticker]
        commands=[command for command in commands if command]

        result={'tickers_to_sell':list(set(tickers_to_sell)),'tickers_to_stop_monitor':list(set(tickers_to_stop_monitor)),'commands':list(set(commands))}
        utils.write_json(result,utils.get_latest_log("COMMANDS"))
        return result,200


application=Flask(__name__)
api=Api(application)
api.add_resource(Commands,"/commands/")
api.add_resource(BackTesting,"/backtesting/<string:ticker>","/backtesting/")
api.add_resource(Retrieve,"/retrieve/<string:data_id>")
api.add_resource(RetrievePastSessions,"/retrievepastsessions/<string:date>/<string:data_id>")
api.add_resource(GetInfo,"/info/<string:info_id>")
api.add_resource(ConfigCommands,"/config/")

if __name__ == "__main__":
    application.run(debug=True,host='192.168.0.14',port=5050)
