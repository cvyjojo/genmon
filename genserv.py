#!/usr/bin/env python
#------------------------------------------------------------
#    FILE: genserv.py
# PURPOSE: Flask app for generator monitor web app
#
#  AUTHOR: Jason G Yates
#    DATE: 20-Dec-2016
#
# MODIFICATIONS:
#------------------------------------------------------------

from flask import Flask, render_template, request, jsonify, session
import sys, signal, os, socket, atexit, configparser
import mylog, myclient

#------------------------------------------------------------
app = Flask(__name__,static_url_path='')

# log errors in this module to a file
log = mylog.SetupLogger("genserv", "/var/log/genserv.log")
HTTPAuthUser = None
HTTPAuthPass = None

#------------------------------------------------------------
@app.route('/', methods=['GET'])
def root():

    if HTTPAuthUser != None and HTTPAuthPass != None:
        if not session.get('logged_in'):
            return render_template('login.html')
        else:
            return app.send_static_file('index.html')
    else:
        return app.send_static_file('index.html')

#------------------------------------------------------------
@app.route('/', methods=['POST'])
def do_admin_login():

    if request.form['password'] == HTTPAuthPass and request.form['username'] == HTTPAuthUser:
        session['logged_in'] = True
        return root()
    else:
        return render_template('login.html')

#------------------------------------------------------------
@app.route("/cmd/<command>")
def command(command):

    if HTTPAuthUser == None or HTTPAuthPass == None:
        return ProcessCommand(command)

    if not session.get('logged_in'):
               return render_template('login.html')
    else:
        return ProcessCommand(command)

#------------------------------------------------------------
def ProcessCommand(command):

    if command in ["status", "outage", "maint", "logs", "monitor", "getbase", "getsitename", "setexercise", "setquiet", "getexercise","setremote", "settime"]:
            finalcommand = "generator: " + command
            try:
                if command == "setexercise":
                    settimestr = request.args.get('setexercise', 0, type=str)
                    finalcommand += "=" + settimestr
                if command == "setquiet":
                    setquietstr = request.args.get('setquiet', 0, type=str)
                    finalcommand += "=" + setquietstr
                if command == "setremote":
                    setremotestr = request.args.get('setremote', 0, type=str)
                    finalcommand += "=" + setremotestr

                data = MyClientInterface.ProcessMonitorCommand(finalcommand)
            except Exception as e1:
                data = "Retry"
                log.error("Error on command function" + str(e1))
            return jsonify(data)

    else:
        return render_template('command_template.html', command = command)


#------------------------------------------------------------
if __name__ == "__main__":
    address='localhost' if len(sys.argv)<2 else sys.argv[1]

    clientport = 0
    try:

        bUseSecureHTTP = False
        bUseSelfSignedCert = True
        SSLContext = None
        HTTPPort = 8000

        config = configparser.RawConfigParser()
        # config parser reads from current directory, when running form a cron tab this is
        # not defined so we specify the full path
        config.read('/etc/genmon.conf')
        # heartbeat server port, must match value in check_generator_system.py and any calling client apps
        if config.has_option('GenMon', 'server_port'):
            clientport = config.getint('GenMon', 'server_port')

        if config.has_option('GenMon', 'usehttps'):
            bUseSecureHTTP = config.getboolean('GenMon', 'usehttps')

        # user name and password require usehttps = True
        if bUseSecureHTTP:
            if config.has_option('GenMon', 'http_user'):
                HTTPAuthUser = config.get('GenMon', 'http_user')

            if config.has_option('GenMon', 'http_pass'):
                HTTPAuthPass = config.get('GenMon', 'http_pass')

        if bUseSecureHTTP:
            app.secret_key = os.urandom(12)
            HTTPPort = 443
            if config.has_option('GenMon', 'useselfsignedcert'):
                bUseSelfSignedCert = config.getboolean('GenMon', 'useselfsignedcert')

                if bUseSelfSignedCert:
                    SSLContext = 'adhoc'
                else:
                    SSLContext = (config.get('GenMon', 'certfile'), config.get('GenMon', 'keyfile'))
            else:
                # if we get here then usehttps is enabled but not option for useselfsignedcert
                # so revert to HTTP
                HTTPPort = 8000

        else:
            HTTPPort = 8000

    except Exception as e1:
        log.error("Missing config file or config file entries: " + str(e1))

    MyClientInterface = myclient.ClientInterface(host = address,port=clientport, log = log)
    while True:
        try:

            app.run(host="0.0.0.0", port=HTTPPort, threaded = True, ssl_context=SSLContext)

        except Exception as e1:
            log.error("Error in app.run:" + str(e1))
