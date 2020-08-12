from flask import Flask,send_from_directory,jsonify
from flask_restful import Api,Resource,abort,reqparse
import utils
import os.path
import json

OUTPUT_DIR="./output/"
OUTPUT_DIR_COMMANDS=OUTPUT_DIR+"ALGO_COMMANDS_LOG_{}.txt".format(utils.date_now_filename())

commands_parser=reqparse.RequestParser()
commands_parser.add_argument("tickers",type=str,help="Ticker of which you want to sell all currently owned stocks.")
commands_parser.add_argument("commands",type=str,help="General commands you want to pass.")


class Plot(Resource):
    def get(self,ticker):
        plotpath=utils.get_plot(ticker)
        if plotpath==None:
            abort(404,message="Plot for {} does not exist.".format(ticker.upper()))
        filename=os.path.basename(plotpath)
        return send_from_directory("/Users/glennviroux/Documents/VSCode/algoTrading/output/plots/",filename,attachment_filename=filename)

class Log(Resource):
    def get(self):
        logpath=utils.get_latest_log("TRADING")
        if logpath==None:
            abort(404,message="Log does not exist.")
        dirname=os.path.dirname(logpath)
        filename=os.path.basename(logpath)
        return send_from_directory(dirname,filename,attachment_filename=filename)

class Status(Resource):
    def get(self):
        statuspath=utils.get_latest_log("STATUS")
        if statuspath==None:
            abort(404,message="No status log exists.")
        dirname=os.path.dirname(statuspath)
        filename=os.path.basename(statuspath)
        return send_from_directory(dirname,filename,attachment_filename=filename)

class PlotData(Resource):
    def get(self):
        plotdatapath=utils.get_latest_log("PLOTDATA")
        if plotdatapath==None:
            abort(404,message="No plotdata log exists.")
        dirname=os.path.dirname(plotdatapath)
        filename=os.path.basename(plotdatapath)
        return send_from_directory(dirname,filename,attachment_filename=filename)

class Overview(Resource):
    def get(self):
        overviewpath=utils.get_latest_log("OVERVIEW")
        if overviewpath==None:
            abort(404,message="No overview log exists.")
        dirname=os.path.dirname(overviewpath)
        filename=os.path.basename(overviewpath)
        return send_from_directory(dirname,filename,attachment_filename=filename)

class Commands(Resource):
    def post(self):
        commands_log=utils.get_latest_log("COMMANDS")
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
        
        for ticker in tickers:
            print(type(ticker))
            print(ticker)

        tickers=[ticker for ticker in tickers if ticker]
        commands=[command for command in commands if command]

        result={'tickers':list(set(tickers)),'commands':list(set(commands))}
        utils.write_json(result,OUTPUT_DIR_COMMANDS)
        return result,200



def start():
    app=Flask(__name__)
    api=Api(app)

    api.add_resource(Plot,"/plots/<string:ticker>")
    api.add_resource(Log,"/log/")
    api.add_resource(Status,"/status/")
    api.add_resource(PlotData,"/plotdata/")
    api.add_resource(Overview,"/overview/")
    api.add_resource(Commands,"/commands/")

    app.run(debug=True,host='192.168.1.37',port=5050)

start()
