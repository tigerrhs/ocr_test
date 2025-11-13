# -*- coding: utf-8 -*-
#first_change
from sys import exit
import logging
import urllib3
from flask import Flask
import importlib
import ezpdf_license
import lb

common_module = importlib.import_module("common_module")
dbquery = importlib.import_module("dbquery")

get_logger = common_module.get_logger
make_db = dbquery.make_db

if ezpdf_license.licenseCheck('./lice/licenseFile.dat', 'LEA001') == False:
    print("라이센스 문제입니다. 유니닥스에 문의 바랍니다.")
    exit()
else:
    print("passed license check")

app = Flask(__name__)

logger = get_logger()
log = logging.getLogger('werkzeug') # 관리자 웹 추가 [End]

def run(host, port):
    # Flask 시작
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    app.run(host, port, debug=False, threaded=True)

if __name__ == '__main__':
    logger.info("UniOCR RestAPI Server started")
    
    make_db() #새로운 테이블 추가를 위해 무조건 타게 한다.
    openport = lb.open_port()
    run(host='0.0.0.0', port=openport)