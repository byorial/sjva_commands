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
from flask import Blueprint, request
from framework import app, py_urllib
from system.model import ModelSetting as SystemModelSetting
from rclone.logic import Logic as LogicRclone
from lib_gdrive import LibGdrive
from plex.model import ModelSetting as PlexModelSetting
import plex

##########################################################################################
# 사용자 설정값
##########################################################################################
# 종영처리할 대상경로:종영시 이동 경로
TARGET = {u'gdrive:/PDS/TV/00.국내TV(방송중)/드라마':u'gdrive:/PDS/TV/01.국내드라마(종영)'}
# 여러개 입력 시 샘플
"""
TARGET = {u'gdrive:/PDS/TV/00.국내TV(방송중)/드라마':u'gdrive:/PDS/TV/01.국내드라마(종영)', 
        u'gdrive:/PDS/TV/00.국내TV(방송중)/일본드라마':u'gdrive:/PDS/TV/02.해외드라마'}
"""

# 테스트시 True, 실제실행시 False
DRYRUN = True

# 경로변환 규칙: remote경로, Plex서버상의 경로
REMOTE_PATH_RULE = {u'gdrive:/PDS':u'/mnt/gdrive'}
#REMOTE_PATH_RULE = {u'gdrive:/PDS':u'P:'} # for window plex 
#REMOTE_PATH_RULE = {u'gdrive:/PDS':u'/mnt/gdrive', u'tdrive:/PDS':u'/mnt/tdrive'} # 여러개입력시 샘플

# PLEX관련 설정 --------------------------------------------------------------------------
# 스캔명령 전송 여부: True:스캔명령전송, False: 스캔명령 전송안함
PLEX_SCAN_SEND = True 
# 라이브러리 삭제 여부: True:이동후 이전 라이브러리의 항목을 Plex에서 삭제함, False-직접삭제해야함
PLEX_DELETE_LIB = True 
# CALLBACK URI: 스캔완료 Callback을 받을 URI:
CALLBACK_URI = '/callback'
##########################################################################################

# global variables
bp = Blueprint('mycallback', 'mycallback', url_prefix=CALLBACK_URI, template_folder=os.path.join(os.path.dirname(__file__), 'templates'))

remotes = []
parents = {}
services = {}

@bp.route('/scan_completed', methods=['GET','POST'])
def callback_handler():
    global PLEX_DELETE_LIB
    try:
        log('callback handler!!!!!!')
        if request.method == 'GET':
            log(request.args)
            callback_id = request.args.get('id')
            filename    = request.args.get('filename')
        else:
            log(request.form)
            callback_id = request.form['id']
            filename = request.form['filename']

        base_url = '{s}/library/metadata/{m}?includeExternalMedia=1&X-Plex-Product=Plex%20Web&X-Plex-Product=Plex%20Web&X-Plex-Version=4.51.1&X-Plex-Platform=Chrome&X-Plex-Platform-Version=88.0&X-Plex-Sync-Version=2&X-Plex-Features=external-media%2Cindirect-media&X-Plex-Model=bundled&X-Plex-Device=Windows&X-Plex-Device-Name=Chrome&X-Plex-Device-Screen-Resolution=1920x937%2C1920x1080&X-Plex-Language=ko&X-Plex-Drm=widevine&X-Plex-Text-Format=plain&X-Plex-Provider-Version=1.3&X-Plex-Token={t}'
        server = PlexModelSetting.get('server_url')
        token = PlexModelSetting.get('server_token')
        devid = PlexModelSetting.get('machineIdentifier')
        action, section_id, metadata_id = callback_id.split('|')
        log(u'콜백수신: {},{},{},{}'.format(action, section_id, metadata_id, filename))
        if action == 'REMOVE':
            if PLEX_DELETE_LIB:
                if plex.LogicNormal.os_path_exists(filename) == False: # 존재하지 않는 경우만 삭제
                    log(u'콕백처리: 라이브러리삭제({}:{})'.format(filename, metadata_id))
                    url = base_url.format(s=server, m=metadata_id, t=token, d=devid)
                    headers = { "Accept": 'application/json',
                            "Accept-Encoding": 'gzip, deflate, br',
                            "Accept-Language": 'ko',
                            "Connection": 'keep-alive',
                            "User-Agent": 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.182 Mobile Safari/537.36' }

                    res = requests.delete(url, headers=headers)
                    log('[CALLBACK] DELETE-Response Status Code: {}'.format(res.status_code))

                    if res.status_code != 200:
                        log('[CALLBACK] REMOVE-failed to delete metadata({},{})'.format(metadata_id, filename))
        else:
            log('CALLBACK: ADD-completed {}'.format(filename))

        return 'ok'
    except Exception as e:
        log('Exception %s', e)
        log(traceback.format_exc())
        return 'ok'

def strftime_in_kst(datetimeutc, date_format, time_diff=0):
    return (datetimeutc + timedelta(hours=time_diff)).strftime(date_format)

def init_gdrive():
    global remotes, parents, services
    remotes = LogicRclone.load_remotes()

    for orig,dest in TARGET.items():
        for rpath in [orig, dest]:
            remote = get_rclone_remote(rpath)
            if remote == None:
                log(u'처리오류: rclone.conf의 remote 정보를 확인하세요')
                return False

            if remote['name'] not in services:
                service = LibGdrive.auth_by_rclone_remote(remote)
                if services == None:
                    log(u'처리오류: Gdrive API 인증실패- rclone설정을 확인하세요')
                    return False
                log(u'인증성공: Gdrive API 인증완료: remote({})'.format(remote['name']))
                services[remote['name']] = service

            if rpath not in parents:
                if 'team_drive' in remote: folder_id = LibGdrive.get_folder_id_by_path(rpath, service=service, teamdrive_id=remote['team_drive'])
                else: folder_id = LibGdrive.get_folder_id_by_path(orig, service=service)
                if folder_id == None:
                    log(u'처리오류: PATH(%s) folder_id 획득실패' % rpath)
                    return False
                parents[rpath] = folder_id
                log(u'폴더정보: PATH({}) folder_id({})'.format(rpath, folder_id))

    return True

def move_ended_item(orig_path, dest_path):
    global DRYRUN
    try:
        global services, parents
        remote = get_rclone_remote(orig_path)
        service = services[remote['name']]
        old_parent_id = parents[os.path.dirname(orig_path)]
        new_parent_id = parents[os.path.dirname(dest_path)]
        info = LibGdrive.get_file_info_with_name_parent(os.path.basename(orig_path), old_parent_id, service=service)
        if info['ret'] != 'success':
            log(u'존재하지 않는 파일: {}'.format(os.path.dirname(orig_path)))
            return False
        folder_id = info['data']['id']
        log(u'폴더이동: 폴더({}), 폴더ID({})'.format(orig_path, folder_id))
        log(u'이동  전: 폴더({}), 폴더ID({})'.format(os.path.dirname(orig_path), old_parent_id))
        log(u'이동  후: 폴더({}), 폴더ID({})'.format(os.path.dirname(dest_path), new_parent_id))
        if DRYRUN == False:
            ret = LibGdrive.move_file(folder_id, old_parent_id, new_parent_id, service=service)
            if ret['ret'] != 'success':
                log(u'이동실패: 로그를 확인하세요.')
                return False
        log(u'이동완료: 폴더({}), 폴더ID({})'.format(os.path.dirname(dest_path), folder_id))
        return True
    except Exception as e:
        log('Exception %s', e)
        log(traceback.format_exc())
        return False

def get_rclone_remote(remote_path):
    global remotes
    remote_name = remote_path[:remote_path.find(':')]
    for remote in remotes:
        if remote['name'] == remote_name:
            return remote
    return None
                
def get_dest_root(rpath):
    global TARGET
    try:
        ret = TARGET[rpath]
        return ret
    except KeyError:
        log('이동제외: 대상경로 아님(%s)' % rpath)
    except Exception as e:
        log('Exception %s', e)
        log(traceback.format_exc())
        return None

def get_remote_path(plexpath):
    global REMOTE_PATH_RULE

    for rpath,ppath in REMOTE_PATH_RULE.items():
        if plexpath.startswith(ppath):
            ret = plexpath.replace(ppath, rpath)
            if plexpath[0] != '/':
                ret = ret.replace('\\','/')
            return ret.replace('//', '/').replace('\\\\', '\\')
    return plexpath


def get_plex_path(remotepath):
    global REMOTE_PATH_RULE

    for rpath,ppath in REMOTE_PATH_RULE.items():
        if remotepath.startswith(rpath):
            ret = remotepath.replace(rpath, ppath)
            if ret[0] != '/':
                ret = ret.replace('/','\\')
            return ret.replace('//', '/').replace('\\\\', '\\')
    return remotepath

def get_root_path(section_id, location_id):
    query = "select root_path from section_locations where id = {lid} and library_section_id = {sid}".format(lid=location_id, sid=section_id)
    url = '%s/:/plugins/com.plexapp.plugins.SJVA/function/db_query?query=%s&X-Plex-Token=%s' % (PlexModelSetting.get('server_url'), py_urllib.quote(query.encode('utf8')), PlexModelSetting.get('server_token'))
    data = requests.get(url).json()
    if data['ret'] is True:
        return data['data'][0]
    return None

def get_sub_path(directory_id, path=None):
    query = "select parent_directory_id, library_section_id, path from directories where id = {directory_id}".format(directory_id=directory_id)
    url = '%s/:/plugins/com.plexapp.plugins.SJVA/function/db_query?query=%s&X-Plex-Token=%s' % (PlexModelSetting.get('server_url'), py_urllib.quote(query.encode('utf8')), PlexModelSetting.get('server_token'))
    data = requests.get(url).json()
    #log(data)
    if len(data['data']) > 0:
        pid, sid, p = data['data'][0].split('|')

        if pid == '': return path
        if path is not None: p = os.path.join(p, path)

        return get_sub_path(int(pid), path=p)
    return None

def get_library_path(section_id, location_id, directory_id):
    root_path = get_root_path(section_id, location_id)
    if not root_path: return None, None
    #log('root_path:(%s)' % root_path)

    sub_path  = get_sub_path(directory_id)
    if not sub_path: return None, None
    #log('sub_path: (%s)' % sub_path)

    return root_path, sub_path

def get_section_id(path):
    section_id = plex.LogicNormal.get_section_id_by_filepath(path)
    return int(section_id)

def get_program_metadata_id(meta_id):
    try:                                            
        for i in range(4):
            query = 'SELECT id,parent_id,metadata_type from metadata_items where id="{}"'.format(meta_id)
            ret = plex.LogicNormal.execute_query(query)                  
            if ret['ret'] != True:
                log('failed to get parent_id:({})'.format(meta_id))
                return None             
            #log(ret['data'])
            mid, pid, mtype = ret['data'][0].split('|')
            if mtype == '2':
                meta_id = mid
                break

            meta_id = pid
            #if ret['data'][0] == u'': break
            #meta_id = ret['data'][0]
        return meta_id

    except Exception as e:
        logger.debug('Exception:%s', e)                  
        logger.debug(traceback.format_exc())
        return None 

def get_ended_dirlist():
    query = "select MM.metadata_item_id, MP.id, MP.media_item_id, MP.directory_id, MP.file, MM.library_section_id, MM.section_location_id from media_parts MP, media_items MM\
                where MP.media_item_id in( \
                select M.id from media_items M, \
                (select MI1.id from metadata_items MI1, \
                (select MI2.id, MI2.parent_id from metadata_items MI2, \
                (select id from metadata_items MI1 where title like '[종영]%') MI1\
                where MI2.parent_id = MI1.id) MIX \
                where MI1.parent_id = MIX.id) MX \
                where MX.id = M.metadata_item_id) and MP.media_item_id = MM.id\
                group by MP.directory_id"

    url = '%s/:/plugins/com.plexapp.plugins.SJVA/function/db_query?query=%s&X-Plex-Token=%s' % (PlexModelSetting.get('server_url'), py_urllib.quote(query.encode('utf8')), PlexModelSetting.get('server_token'))
    try:
        data = requests.get(url).json()
        dirlist = list()

        for item in data['data']:
            metadata_id, media_part_id, media_item_id, directory_id, file_path, section_id, location_id = item.split('|')
            log(u'대상경로: dir(%s), path(%s), meta_id(%s)' % (directory_id, os.path.dirname(file_path), metadata_id))
            program_meta_id = None
            program_meta_id = get_program_metadata_id(metadata_id)
            if program_meta_id == None:
                log(u'처리오류: 프로그램 메타정보 획득 실패')
                continue
            log(u'메타정보: 프로그램 메타데이터ID({})'.format(program_meta_id))
            ditem = {'directory_id':int(directory_id), 'section_id':int(section_id), 'location_id':int(location_id), 'metadata_id':int(program_meta_id) }
            if ditem not in dirlist:
                dirlist.append(ditem)

        return dirlist

    except Exception as e:
        log('Exception %s', e)
        log(traceback.format_exc())
        data = None
    return data

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

def run(args):
    global DRYRUN, PLEX_SCAN_SEND
    try:
        log('- 1: 구글드라이브 인증 --------------------------------------------------------------')
        if init_gdrive() == False:
            log(u'처리오류: lib_gdrive 초기화 실패:lib_gdrive설치, rclone사용설정 필요')
            return

        log('- 2. Plex 종영 프로그램 조회---------------------------------------------------------')
        dirlist = get_ended_dirlist()
        log('조회결과: {} 건'.format(str(len(dirlist))))
        log('- 3. 종영프로그램 이동 처리----------------------------------------------------------')
        count = 0
        skip_count = 0
        for item in dirlist:
            #log(item)
            rpath, spath = get_library_path(item['section_id'], item['location_id'], item['directory_id'])
            if rpath is None:
                log(u'처리오류: 라이브러리 경로 획득 실패(section_id:%s, location_id:%s)' %(item['section_id'], item['location_id']))
                continue
            dest_root = get_dest_root(get_remote_path(rpath))
            if dest_root is None:
                skip_count += 1
                #log('failed to dest_root: non-target(%s/%s' % (rpath, spath))
                continue

            # rclone move
            orig_path = os.path.join(get_remote_path(rpath), spath)
            dest_path = os.path.join(dest_root, spath)

            log('-------------------------------------------------------------------------------------')
            log('원본경로: (%s)' % orig_path)
            log('이동경로: (%s)' % dest_path)

            ret = move_ended_item(orig_path, dest_path)
            if ret:
                count += 1
                log('- 4. PLEX SCAN 명령 전송 ----------------------------------------------------------------')
                if DRYRUN == True or PLEX_SCAN_SEND == False:
                    log(u'스캔전송: 스킵처리 - dryrun({}),scan_send({})'.format(str(DRYRUN), str(PLEX_SCAN_SEND)))
                    continue
                pname = u'proc_plex_ended'
                callback_url='{}{}'.format(SystemModelSetting.get('ddns'), CALLBACK_URI + '/scan_completed')
                for action in [u'REMOVE', u'ADD']:
                    if action == u'REMOVE':
                        plex_path = get_plex_path(orig_path)
                        section_id = int(item['section_id'])
                        callback_id = '{}|{}|{}'.format(action,str(section_id),str(item['metadata_id']))
                    else: # ADD
                        plex_path = get_plex_path(dest_path)
                        section_id = get_section_id(plex_path)
                        callback_id = '{}|{}|{}'.format(action, str(section_id),'None')
                        if section_id == -1:
                            log(u'처리오류: 종영폴더의 section_id 획득 실패({}:{})'.format(action, plex_path))
                            continue
                    ret = plex.Logic.send_scan_command2(pname, section_id, plex_path, callback_id, action, pname, callback_url=callback_url)
                    log(u'스캔전송: callback({}), path({})'.format(callback_id, plex_path))
            log('-------------------------------------------------------------------------------------')

    except Exception as e:
        log('Exception %s', e)
        log(traceback.format_exc())

def callback_function(callback_id, filename):
    global PLEX_DELETE_LIB
    try:
        base_url = '{s}/library/metadata/{m}?includeExternalMedia=1&X-Plex-Product=Plex%20Web&X-Plex-Product=Plex%20Web&X-Plex-Version=4.51.1&X-Plex-Platform=Chrome&X-Plex-Platform-Version=88.0&X-Plex-Sync-Version=2&X-Plex-Features=external-media%2Cindirect-media&X-Plex-Model=bundled&X-Plex-Device=Windows&X-Plex-Device-Name=Chrome&X-Plex-Device-Screen-Resolution=1920x937%2C1920x1080&X-Plex-Language=ko&X-Plex-Drm=widevine&X-Plex-Text-Format=plain&X-Plex-Provider-Version=1.3&X-Plex-Token={t}'
        server = PlexModelSetting.get('server_url')
        token = PlexModelSetting.get('server_token')
        devid = PlexModelSetting.get('machineIdentifier')

        action, section_id, metadata_id = callback_id.split('|')
        log(u'콜백수신: {},{},{},{}'.format(action, section_id, metadata_id, filename))
        if action == 'REMOVE':
            if PLEX_DELETE_LIB:
                if plex.LogicNormal.os_path_exists(filename) == False: # 존재하지 않는 경우만 삭제
                    log(u'콜백처리: 라이브러리삭제({}:{})'.format(filename, metadata_id))
                    url = base_url.format(s=server, m=metadata_id, t=token, d=devid)
                    headers = { "Accept": 'application/json',
                            "Accept-Encoding": 'gzip, deflate, br',
                            "Accept-Language": 'ko',
                            "Connection": 'keep-alive',
                            "User-Agent": 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.182 Mobile Safari/537.36' }

                    res = requests.delete(url, headers=headers)
                    log('[CALLBACK] DELETE-Response Status Code: {}'.format(res.status_code))

                    if res.status_code != 200:
                        log('[CALLBACK] REMOVE-failed to delete metadata({},{})'.format(metadata_id, filename))
        else:
            log('CALLBACK: ADD-completed {}'.format(filename))

    except Exception as e:
        log('Exception %s', e)
        log(traceback.format_exc())

def main(*args, **kwargs):
    global logger
    if 'logger' in kwargs:
        logger = kwargs['logger']
        log('=========== SCRIPT START ===========')
        rule_list = [x.rule for x in app.url_map.iter_rules()]
        if (CALLBACK_URI + '/scan_completed') not in rule_list:
            log(u'콜백등록: {}'.format(CALLBACK_URI+'/scan_completed'))
            app.register_blueprint(bp)
            app.add_template_filter(strftime_in_kst)

        run(args)
        """
        if 'register' in args:
            app.register_blueprint(bp)
            app.add_template_filter(strftime_in_kst)
            log('route register success!!!!!!!!!!!!')
            return
        else:
            run(args)
        """
        log('=========== SCRIPT END ===========')
    else:
        log('LOAD 스크립트로 실행해 주세요!!!!!!!!!!!!!!!!!!!!!!!!!!')

if __name__ == "__main__":
    main()
