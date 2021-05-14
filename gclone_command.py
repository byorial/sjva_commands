# -*- coding: utf-8 -*-
#!/usr/bin/env python
import sys
if __name__== "__main__":
    if sys.version_info[0] == 2:
        reload(sys)
        sys.setdefaultencoding('utf-8')

logger = None
import os, traceback
import re

# SJVA
from rclone_expand.model import ModelSetting
from rclone_expand.logic_gclone import LogicGclone

#######################################################################################
# 사용자 설정
#######################################################################################
# 실행방식 결정: True - rclone_expand 큐에 추가, False - 명령어 직접 실행(copy, move, sync 가능)
use_rclone_expand = True
# cmd_type: copy, move, sync: use_rclone_expand=False 인경우만 유효함: Thread로 동작
cmd_type = 'copy'
# gclone 명령어 경로: 기본 rclone_expand 설정값 가져옴: '/usr/bin/gclone' 형태로 지정 가능
gclone_path = ModelSetting.get('gclone_path')
#gclone_path = '/usr/bin/gclone'

# 작업목록 대상 설정: ['원본폴더ID', '대상폴더ID', '하위폴더명']
# ex) ['11111', '22222', u'TV'] -> gc:{11111}|gc{22222}/TV
# 하위폴더명은 옵션: 없는 경우 생략 u'' 형태로 지정
job_list = [
        ['1qfFbzTZjRJ7UBHLtC-RIPvF0BvNTI31N', '124wMe0zU67jOo4scCBevPJiNzgjCrp2j'],
    ]

#######################################################################################
def run(args):
    global target_list, gclone_path, config_path
    try:
        if use_rclone_expand:
            # rclone_expand queue에 추가
            for job in job_list:
                subdir = None
                if len(job) == 3: subdir = job[2] if job[2][0] == '/' else '/'+job[2]
                qstr = u'gc:{%s}|gc:{%s}%s' % (job[0], job[1], subdir if subdir is not None else '')
                log('append to rclone_expand job queue:%s' % qstr)
                LogicGclone.queue_append([qstr])
        else:
            # command 직접 실행
            import subprocess
            config_path = ModelSetting.get('gclone_config_path')
            user_option = ModelSetting.get_list('gclone_user_option', ' ')
            fix_option = ModelSetting.get_list('gclone_fix_option', ' ')
            rx = r'\s*\*\s((?P<folder>.*)\/)?(?P<name>.*?)\:\s*(?P<percent>\d+)\%\s*\/(?P<size>\d.*?)\,\s*(?P<speed>\d.*?)\,\s*((?P<rt_hour>\d+)h)*((?P<rt_min>\d+)m)*((?P<rt_sec>.*?)s)*'
            if LogicGclone.is_fclone():
                fix_option = ['--stats','1s','--log-level','NOTICE','--stats-log-level','NOTICE']
            for job in job_list:
                subdir = None
                if len(job) == 3: subdir = job[2] if job[2][0] == '/' else '/'+job[2]
                command = [
                        gclone_path,
                        '--config',
                        config_path,
                        cmd_type,
                        'gc:{%s}' % job[0],
                        'gc:{%s}%s' % (job[1], subdir if subdir is not None else '')]
                command += fix_option
                command += user_option
                log(command)
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, bufsize=1)
                with process.stdout:
                    for line in iter(process.stdout.readline, ''):
                        match = re.compile(rx).search(line)
                        if match: continue
                        if line.startswith('Transferring:'): continue
                        log(line.replace('\n',''))
                        sys.stdout.flush()
                    process.wait()

    except Exception as e:
        log('Exception %s', e)
        log(traceback.format_exc())

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
        run(args)

if __name__ == "__main__":
    main()
