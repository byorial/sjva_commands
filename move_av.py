# -*- coding: utf-8 -*-
#!/usr/bin/env python
import sys
if __name__ == "__main__":
    reload(sys)
    sys.setdefaultencoding('utf-8')
logger = None
import os, traceback
import re

# SJVA
from lib_gdrive import LibGdrive
from tool_expand import ToolExpandFileProcess
from rclone.logic import Logic as LogicRclone

# 3rd party
import json

########################################################################
# 
########################################################################
remote_name = u'gdrive'
label_folder_id = u'1vZvGfxDSocmLY1iwU6-CpypjMYcrOP2H'
vr_folder_id = u'1IRQmNs_qcEbjz8KAI8l6liMS-M-Pu3Q6'
vr_labels = [ "AJVR" ,"ATVR" ,"AVERV" ,"AVOPVR" ,"AVVR" ,"BFKB" ,"BIKMVR" ,"BMBBVR" ,"BNVR" ,"BUZ" ,"CACA" ,"CAFR" ,"CAMI" ,"CAPI" ,"CAREM" ,"CASMANI"
        "AJVR" ,"ATVR" ,"AVERV" ,"AVOPVR" ,"AVVR" ,"BFKB" ,"BIKMVR" ,"BMBBVR" ,"BNVR" ,"BUZ" ,"CACA" ,"CAFR" ,"CAMI" ,"CAPI" ,"CAREM" ,"CASMANI" 
        ,"CBIKMV" ,"CCVR" ,"CJVR" ,"CLVR" ,"COSBVR" ,"COSVR" ,"CRVR" ,"DANDYHQVR" ,"DECHA" ,"DOCVR" ,"DOVR" ,"DSVR" ,"DTVR" ,"EBVR" ,"EKAIVR"
        ,"ETVCO" ,"ETVTM" ,"EXBVR" ,"EXVR" ,"FCVR" ,"FSVSS" ,"GASVR" ,"GOPJ" ,"HAY" ,"HNVR" ,"HOTVR" ,"HUNVR" ,"HVR" ,"IPVR" ,"JPSVR" ,"JUVR"
        ,"KAVR" ,"KBVR" ,"KIVR" ,"KIWVR" ,"KMVR" ,"KOLVR" ,"MANIVR" ,"MAXVR" ,"MAXVRH" ,"MDVR" ,"MGVR" ,"MIVR" ,"MMVRN" ,"MOHV" ,"MXVR" ,"NHVR"
        ,"OYCVR" ,"PMAXVR" ,"PPVR" ,"PRDVR" ,"PRVR" ,"PXVR" ,"ROYVR" ,"RVR" ,"SAVR" ,"SCVR" ,"SIVR" ,"SKHVR" ,"STVR" ,"TMAVR" ,"TMVR" ,"TPVR"
        ,"URVRSP" ,"VOVS" ,"VRAD" ,"VRGL" ,"VRKM" ,"VRTB" ,"VRVR" ,"VRVRW" ,"VVVR" ,"WAVR" ,"WOW" ,"WPVR" ,"WVR"]

service = None
########################################################################
def get_rclone_remote(remote_name):
    for remote in remotes:
        if remote['name'] == remote_name:
            return remote
    return None
 
def init_gdrive():
    global service, remote_name, remotes
    remotes = LogicRclone.load_remotes()
    remote = get_rclone_remote(remote_name)
    service = LibGdrive.auth_by_rclone_remote(remote)
    if service == None:
        log(u'처리오류: Gdrive API 인증실패- rclone설정을 확인하세요')
        return False
    log(u'인증성공: Gdrive API 인증완료: remote({})'.format(remote['name']))
    return True

def load_vr_folders():
    global vr_labels, label_folder_id, service
    try:
        folders = {}
        children = LibGdrive.get_children_folders(label_folder_id, service=service)
        for child in children:
            if child['trashed']: continue
            if child['name'] in vr_labels:
                folders[child['name']] = {'id':child['id'],'parent_id':child['parents'][0]}
        log('load_vr_folders: len(%d)' % len(folders))
        return folders
    except Exception as e:
        log('Exception %s', e)
        log(traceback.format_exc())

def load_dst_folders():
    global vr_folder_id, service
    try:
        folders = {}
        children = LibGdrive.get_children_folders(vr_folder_id, service=service)
        log('load_dst_folders: len(%d)' % len(children))
        for child in children:
            if child['trashed']: continue
            if child['name'] in vr_labels:
                folders[child['name']] = child['id']
        return folders

    except Exception as e:
        log('Exception %s', e)
        log(traceback.format_exc())

def run(args):
    global vr_folder_id
    try:
        if init_gdrive() == False:
            log('failed to init gdrive api')
            return
        origs = load_vr_folders()
        dests = load_dst_folders()

        for k,v in origs.items():
            # 이동대상 폴더 미존재: 걍옮기면 됨 
            if k not in dests:
                log('{} 폴더를 VR폴더로 이동'.format(k))
                log('  move {} to {}({})'.format(k, 'VR', vr_folder_id))
                ret = LibGdrive.move_file(v['id'], v['parent_id'], vr_folder_id, service=service)
            # 이동대상 폴더 존재: 자식들을 옮겨야됨
            else:
                log('{} 의 자식폴더들 이동'.format(k))
                children = LibGdrive.get_children(v['id'], service=service)
                for child in children:
                    log('  {} 를 {} 폴더 하위로 이동'.format(child['name'], k))
                    log('  move {} to {}({})'.format(child['name'], k, dests[k]))
                    ret = LibGdrive.move_file(child['id'], child['parents'][0], dests[k], service=service)


    except Exception as e:
        log('Exception %s', e)
        log(traceback.format_exc())

###### 아래는 SJVA command 기본값
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
