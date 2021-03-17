# -*- coding: utf-8 -*-
#!/usr/bin/env python
import sys
if __name__ == "__main__":
    reload(sys)
    sys.setdefaultencoding('utf-8')
logger = None
import os, traceback
import re
import requests
import json

# SJVA
from flask import Blueprint, request, render_template, redirect
from framework import app, py_urllib
from system.model import ModelSetting as SystemModelSetting
from rclone.logic import Logic as LogicRclone
from lib_gdrive import LibGdrive
#import gd_share_client
from gd_share_client.plugin import ModelSetting as GDModelSetting

##########################################################################################
# 사용자 설정값
##########################################################################################
BASIC_REMOTE = u'gdrive:'
REMOTE_PATH_RULE = ['gdrive:/PDS', '/mnt/gdrive']
MY_URL = '/my_upload'
##########################################################################################

# global variables
bp = Blueprint('my_upload', 'my_upload', url_prefix=MY_URL, template_folder=os.path.join(os.path.dirname(__file__), 'templates'))

@bp.route('/', methods=['GET','POST'])
def my_route():
    arg = GDModelSetting.to_dict()
    arg['remote_path'] = REMOTE_PATH_RULE[0]
    arg['local_path'] = REMOTE_PATH_RULE[1]
    return render_template('upload.html', arg=arg)

def strftime_in_kst(datetimeutc, date_format, time_diff=0):
    return (datetimeutc + timedelta(hours=time_diff)).strftime(date_format)

def run(args):
    try:
        rule_list = [x.rule for x in app.url_map.iter_rules()]
        if MY_URL not in rule_list:
            log(u'url_map 등록: {}'.format(MY_URL))
            app.register_blueprint(bp)
            app.add_template_filter(strftime_in_kst)
    except Exception as e:
        log('Exception %s', e)
        log(traceback.format_exc())

##########################################################################################
def log(*args):
    global logger
    try:
        if logger is not None:
            logger.debug(*args)
        if len(args) > 1:
            print(args[0] % tuple([str(x) for x in args[1:]]))
        else:
            print(str(args[0]))
        sys.stdout.flush()
    except Exception as e:
        log('Exception %s', e)
        log(traceback.format_exc())

def main(*args, **kwargs):
    global logger
    if 'logger' in kwargs:
        logger = kwargs['logger']
        log('=========== SCRIPT START ===========')
        run(args)
        log('=========== SCRIPT END ===========')
    else:
        log('LOAD 스크립트로 실행해 주세요!!!!!!!!!!!!!!!!!!!!!!!!!!')

if __name__ == "__main__":
    main()
