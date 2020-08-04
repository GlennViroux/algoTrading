from flask import Flask,send_from_directory,jsonify
from flask_restful import Api,Resource,abort
import utils
import os.path
import json



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
        logpath=utils.get_latest_log()
        if logpath==None:
            abort(404,message="Log does not exist.")
        dirname=os.path.dirname(logpath)
        filename=os.path.basename(logpath)
        return send_from_directory(dirname,filename,attachment_filename=filename)

class Status(Resource):
    def get(self):
        statuspath=utils.get_status_log()
        if statuspath==None:
            abort(404,message="No status log exists.")
        dirname=os.path.dirname(statuspath)
        filename=os.path.basename(statuspath)
        return send_from_directory(dirname,filename,attachment_filename=filename)

class PlotData(Resource):
    def get(self):
        plotdatapath=utils.get_plotdata_log()
        if plotdatapath==None:
            abort(404,message="No plotdata log exists.")
        dirname=os.path.dirname(plotdatapath)
        filename=os.path.basename(plotdatapath)
        return send_from_directory(dirname,filename,attachment_filename=filename)

def start():
    app=Flask(__name__)
    api=Api(app)

    api.add_resource(Plot,"/plots/<string:ticker>")
    api.add_resource(Log,"/log/")
    api.add_resource(Status,"/status/")
    api.add_resource(PlotData,"/plotdata/")

    app.run(debug=False,host='192.168.1.37',port=5050)