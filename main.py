# -*- coding: utf-8 -*-

import os
import logging
from flask import Flask, request, render_template, make_response
from flask_cors import CORS
import pyexcel
import signal
import datetime
import sys
import json
from model import predict, pridict_preload_model, preload_model
from SQL import *
from Bucket import *
from zipfile import ZipFile
from settings import *

RUN_COUNT = 0

# define the app
DebuggingOn = bool(os.getenv('DEBUG', False))  # Whether the Flask app is run in debugging mode, or not.
app = Flask(__name__)
app.config['SECRET_KEY'] = 'comp4312'
CORS(app)  # needed for cross-domain requests, allow everything by default


def sigterm_handler(_signo, _stack_frame):
    print(str(datetime.datetime.now()) + ': Received SIGTERM')


def sigint_handler(_signo, _stack_frame):
    print(str(datetime.datetime.now()) + ': Received SIGINT')
    sys.exit(0)


signal.signal(signal.SIGTERM, sigterm_handler)
signal.signal(signal.SIGINT, sigint_handler)


# HTTP Errors handlers
@app.errorhandler(404)
def url_error(e):
    return """
    Wrong URL!
    <pre>{}</pre>""".format(e), 404


@app.errorhandler(500)
def server_error(e):
    logging.exception('An error occurred during a request.')
    return """
    An internal error occurred: <pre>{}</pre>
    See logs for full stacktrace.
    """.format(e), 500


@app.route('/')
def index():
    return render_template('index2.html')


@app.route('/about')
def about():
    content = "about page test"
    return render_template('about.html', content=content)


@app.route('/application')
def application():
    content = "application page test"
    return render_template('application.html', content=content)


@app.route('/bucket')
def bucket():
    return render_template('Bucket.html', list=web_list_blobs())


@app.route('/archive', methods=('GET', 'POST'))
def response():
    query = "SELECT * FROM Reviews "
    input = ""
    response = ""
    if request.method == 'POST':
        if 'Delete' in request.form:
            sql_insert("DELETE FROM Reviews WHERE id=" + request.form['Delete'])

        if 'Search' in request.form:
            if request.form['Input'] != "":
                query += "WHERE Description LIKE '%" + request.form['Input'] + "%' "
                if request.form['Response'] == "Happy":
                    query += "AND Response=1 "
                    response = "Happy"
                if request.form['Response'] == "Not Happy":
                    query += "AND Response=0 "
                    response = "Not Happy"
                input = request.form['Input']
            else:
                if request.form['Response'] == "Happy":
                    query += "WHERE Response=1 "
                    response = "Happy"
                if request.form['Response'] == "Not Happy":
                    query += "WHERE Response=0 "
                    response = "Not Happy"

        if 'Download' in request.form:
            if request.form['Input'] != "":
                query += "WHERE Description LIKE '%" + request.form['Input'] + "%' "
                if request.form['Response'] == "Happy":
                    query += "AND Response=1 "
                if request.form['Response'] == "Not Happy":
                    query += "AND Response=0 "
            else:
                if request.form['Response'] == "Happy":
                    query += "WHERE Response=1 "
                if request.form['Response'] == "Not Happy":
                    query += "WHERE Response=0 "
            query += "order by id desc"
            data = sql_to_string(query)
            sheet = pyexcel.get_sheet(file_type="csv", file_content=data)
            outfile = make_response(sheet.csv)
            outfile.headers["Content-Disposition"] = "attachment; filename=Hotel_Reviews.csv"
            outfile.headers["Content-type"] = "text/csv"
            return outfile
        if 'SavetoGCP' in request.form:
            if request.form['Input'] != "":
                query += "WHERE Description LIKE '%" + request.form['Input'] + "%' "
                if request.form['Response'] == "Happy":
                    query += "AND Response=1 "
                if request.form['Response'] == "Not Happy":
                    query += "AND Response=0 "
            else:
                if request.form['Response'] == "Happy":
                    query += "WHERE Response=1 "
                if request.form['Response'] == "Not Happy":
                    query += "WHERE Response=0 "
            data = sql_to_string(query + "order by id desc")
            upload_file(request.form['Name'] + ".csv", data)

    r1 = ""
    r2 = ""
    r3 = ""
    if response == "Happy":
        r1 = "checked"
    else:
        if response == "Not Happy":
            r2 = "checked"
        else:
            r3 = "checked"
    query += "order by id desc"
    table = make_table_response(query)
    return render_template('response.html', table=table, input=input, response=response, r1=r1, r2=r2, r3=r3)


@app.route('/run', methods=('GET', 'POST'))
def run():
    content = ""
    result = ""
    if request.method == 'POST':
        content = request.form['input']
        # ---------------Machine-Learning-Here---------------
        # parent_path = os.path.dirname(os.path.abspath(__file__))
        # ml_path = os.path.join(parent_path, "Dataset", "LR.pickle")
        # result, prob = predict(content, ml_path)
        result, prob = pridict_preload_model(content)
        # ---------------------------------------------------
        result = result_conv(result)
        sql_insert("INSERT INTO Reviews (Description, Response) "
                   "VALUES ('" + content.replace("'", "''") + "', " + str(happy_not_toint(result)) + ")")
        result = "Result: " + result

    table = make_table("SELECT * FROM Reviews order by id desc LIMIT 3")
    return render_template('run.html', content=content, table=table, result=result)


def sql_to_string(q):
    obj = "Description,Response\n"
    query = sql_select(q)
    for x in query:
        x = sql_format_response(x)
        obj += "" + x[1] + "," + happy_not_tostr(x[2]) + "\n"
    return obj


def make_table(query):
    table = ""
    query = sql_select(query)
    for x in query:
        x = sql_format_response(x)
        table += "<tr>"
        table += "<td>" + x[1] + "</td>"
        table += "<td>" + happy_not_tostr(x[2]) + "</td>"
        table += "</tr>"
    return table


def make_table_response(query):
    table = ""
    query = sql_select(query)
    for x in query:
        x = sql_format_response(x)
        table += "<tr>"
        table += "<td>" + x[1] + "</td>"
        table += "<td>" + happy_not_tostr(x[2]) + "</td>"
        table += "<td><form method=\"post\"><button type=\"submit\" class=\"btn btn-danger\" name=\"Delete\"value="\
                 + str(x[0]) + ">Delete</button></form></td>"
        table += "</tr>"
    return table


def result_conv(str):
    if str == "happy":
        return "Happy"
    else:
        return "Not Happy"


def happy_not_tostr(value):
    if value == 1:
        return "Happy"
    else:
        return "Not Happy"


def happy_not_toint(str):
    if str == "Happy":
        return 1
    else:
        return 0


def extract_lr():
    path = os.path.dirname(os.path.abspath(__file__))

    if not os.path.exists(os.path.join(path, "Dataset", "LR.pickle")):
        print("LR.zip Not Found -> Extracting")
        zf = ZipFile(os.path.join(path, "Dataset", "LR.zip"), 'r')
        zf.extractall(os.path.join(path, "Dataset"))
        zf.close()
        print("-> Finished Extracting")
    else:
        print("LR.pickle Exists -> Skip Extract")


if __name__ == '__main__':
    # Extract the LR.pickle file if not already extracted
    extract_lr()
    preload_model()
    sql_proxy_run()
    sql_insert("CREATE TABLE Reviews(id int NOT NULL AUTO_INCREMENT, Description BLOB NOT NULL, Response int(1) NOT NULL, PRIMARY KEY (id))")
    create_bk()
    app.run(host=HOST, port=8080, debug=True)


