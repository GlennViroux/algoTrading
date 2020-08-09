from flask import Flask,send_from_directory,jsonify
from flask_restful import Api,Resource,abort,reqparse
import utils
import os.path
import json

OUTPUT_DIR="./output/"
OUTPUT_DIR_TOSELL=OUTPUT_DIR+"ALGO_TOSELL_LOG_{}.txt".format(utils.date_now_filename())

to_sell_parser=reqparse.RequestParser()
to_sell_parser.add_argument("tickers",type=str,help="Ticker of which you want to sell all currently owned stocks.")


class Plot(Resource):
    def get(self,ticker):
        plotpath=utils.get_plot(ticker)
        if plotpath==None:
            abort(404,message="Plot for {} does not exist.".format(ticker.upper()))
        filename=os.path.basename(plotpath)
        print("GLENNY filename",filename)
        print("GLENNY plotpath",plotpath)
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

class ToSell(Resource):
    def post(self):
        selldata_log=utils.get_latest_log("TOSELL")
        existing_data=utils.read_tosell_data(selldata_log)
        if existing_data and len(existing_data['tickers'])>0:
            tickers=existing_data['tickers']
        else:
            tickers=[]

        args=to_sell_parser.parse_args()
        print("GLENNY args {}".format(args))

        args_dict=dict(args)
        print("GLENNY args dict {}".format(args_dict))
        tickers.append(args_dict['tickers'])
        result={'tickers':list(set(tickers))}
        utils.write_json(result,OUTPUT_DIR_TOSELL)
        return result,200


def start():
    app=Flask(__name__)
    api=Api(app)

    api.add_resource(Plot,"/plots/<string:ticker>")
    api.add_resource(Log,"/log/")
    api.add_resource(Status,"/status/")
    api.add_resource(PlotData,"/plotdata/")
    api.add_resource(Overview,"/overview/")
    api.add_resource(ToSell,"/tosell/")

    app.run(debug=False,host='192.168.1.37',port=5050)
