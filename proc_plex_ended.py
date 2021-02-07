# -*- coding: utf-8 -*-
#!/usr/bin/env python
import sys
if __name__ == "__main__":
    reload(sys)
    sys.setdefaultencoding('utf-8')
logger = None
import os, traceback
import shutil
import re
import requests
import urllib
import json

# 종영처리할 대상경로:종영시 이동 경로
TARGET = {u'gdrive:/PDS/TV/00.국내TV(방송중)/드라마':u'gdrive:/PDS/TV/01.국내드라마(종영)'}
        #u'gdrive:/PDS/TV/00.국내TV(방송중)/일본드라마':u'gdrive:/PDS/TV/02.해외드라마'}
        #u'gdrive:/PDS/TV/00.국내TV(방송중)/예능':u'gdrive:/PDS/TV/04.국내예능-완결',

RCLONE_FLAG = True                                     # RCLONE_FLAG: True - rclone move로 이동, False: mv로 이동
DRYRUN = False                                           # 테스트시 True, 실제실행시 False
REMOTE_PATH_RULE = ['gdrive:/PDS', 'P:']	        # 경로변환 규칙: remote경로, Plex서버상의 경로
RCLONE_PATH = '/opt/SJVA2/bin/Linux/rclone'	        # rclone 명령어 경로
RCLONE_CONF_PATH = '/opt/SJVA2/data/db/rclone.conf'	# rclone.conf 경로
# 로컬경로, Plex경로
PLEX_PATH_RULE = ['/mnt/gdrive', 'P:']

def move_ended_item(orig_path, dest_path):
    global RCLONE_PATH, RCLONE_CONF_PATH, DRYRUN
    from system.logic_command import SystemLogicCommand

    command = [RCLONE_PATH,
            '--config', RCLONE_CONF_PATH,
            'move', orig_path, dest_path,
            '--drive-server-side-across-configs=true',
            '--delete-after',
            '-v']
    if DRYRUN: command.append('--dry-run')

    log(command)

    return_log = SystemLogicCommand.start('종영프로그램 이동', [['msg', '잠시만 기다리세요'], command, ['msg', 'Rclone 명령을 완료하였습니다.']], wait=True)
    ret = {'percent': 0}
    log(return_log)
    for tmp in return_log:
        if tmp.find('Transferred') != -1 and tmp.find('100%') != -1:
            log(tmp)
            ret['percent'] = 100
            break
        elif tmp.find('Checks:') != -1 and tmp.find('100%') != -1:
            ret['percent'] = 100
            break

    if ret['percent'] == 100:
        command = [RCLONE_PATH, '--config', RCLONE_CONF_PATH, 'lsjson', dest_path, '--dirs-only']
        ret['lsjson'] = SystemLogicCommand.execute_command_return(command, format='json')
        tmp = dest_path.split('/')[-1]
        for item in ret['lsjson']:
            if item['Name'] == tmp:
                command = [RCLONE_PATH,
                 '--config',
                 RCLONE_CONF_PATH,
                 'lsjson',
                 dest_path + item['Path'],
                 '-R',
                 '--files-only']
                logger.debug(command)
                ret['lsjson'] = SystemLogicCommand.execute_command_return(command, format='json')
                ret['lsjson'] = sorted(ret['lsjson'], key=lambda k: k['Path'])
                break
    return ret
                
def get_dest_root(rpath):
    global TARGET
    try:
        ret = TARGET[rpath]
        return ret
    except KeyError:
        log('SKIP: 대상경로 아님(path:%s)' % rpath)
    except Exception as e:
        log('Exception %s', e)
        log(traceback.format_exc())
        return None

def get_remote_path(filepath):
    global REMOTE_PATH_RULE

    tmp = REMOTE_PATH_RULE
    ret = filepath.replace(tmp[1], tmp[0])
    if filepath[0] != '/':
        ret = ret.replace('\\', '/')
    return ret.replace('//', '/').replace('\\\\', '\\')

# gdrive:/ --> /mnt/gdrive
def get_local_path(filepath):
    global REMOTE_PATH_RULE
    global PLEX_PATH_RULE

    tmp = REMOTE_PATH_RULE
    ret = filepath.replace(tmp[0], tmp[1])
    if filepath[0] != '/':
        ret = ret.replace('\\', '/')
    ret = ret.replace('//', '/').replace('\\\\', '\\')
    return get_localpath_from_plexpath(ret)

# P:/ --> /mnt/gdrive
def get_localpath_from_plexpath(filepath):
    global PLEX_PATH_RULE

    tmp = PLEX_PATH_RULE
    ret = filepath.replace(tmp[1], tmp[0])
    if filepath[0] != '/':
        ret = ret.replace('\\', '/')
    return ret.replace('//', '/').replace('\\\\', '\\')



def get_root_path(section_id, location_id):
    from plex.model import ModelSetting
    import plex

    query = "select root_path from section_locations where id = {lid} and library_section_id = {sid}".format(lid=location_id, sid=section_id)
    url = '%s/:/plugins/com.plexapp.plugins.SJVA/function/db_query?query=%s&X-Plex-Token=%s' % (ModelSetting.get('server_url'), urllib.quote(query.encode('utf8')), ModelSetting.get('server_token'))
    data = requests.get(url).json()
    if data['ret'] is True:
        return data['data'][0]
    return None

def get_sub_path(directory_id, path=None):
    from plex.model import ModelSetting
    import plex

    query = "select parent_directory_id, library_section_id, path from directories where id = {directory_id}".format(directory_id=directory_id)
    url = '%s/:/plugins/com.plexapp.plugins.SJVA/function/db_query?query=%s&X-Plex-Token=%s' % (ModelSetting.get('server_url'), urllib.quote(query.encode('utf8')), ModelSetting.get('server_token'))
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

def get_ended_dirlist():
    from plex.model import ModelSetting
    import plex

    query = "select MP.id, MP.media_item_id, MP.directory_id, MP.file, MM.library_section_id, MM.section_location_id from media_parts MP, media_items MM\
                where MP.media_item_id in( \
                select M.id from media_items M, \
                (select MI1.id from metadata_items MI1, \
                (select MI2.id, MI2.parent_id from metadata_items MI2, \
                (select id from metadata_items MI1 where title like '[종영]%') MI1\
                where MI2.parent_id = MI1.id) MIX \
                where MI1.parent_id = MIX.id) MX \
                where MX.id = M.metadata_item_id) and MP.media_item_id = MM.id"

    url = '%s/:/plugins/com.plexapp.plugins.SJVA/function/db_query?query=%s&X-Plex-Token=%s' % (ModelSetting.get('server_url'), urllib.quote(query.encode('utf8')), ModelSetting.get('server_token'))
    try:
        data = requests.get(url).json()
        dirlist = list()

        for item in data['data']:
            metadata_id, media_item_id, directory_id, file_path, section_id, location_id = item.split('|')
            log('dir(%s), path(%s)' % (directory_id, file_path))

            ditem = {'directory_id':int(directory_id), 'section_id':int(section_id), 'location_id':int(location_id) }
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
    global DRYRUN
    try:
        dirlist = get_ended_dirlist()
        for item in dirlist:
            log(item)
            rpath, spath = get_library_path(item['section_id'], item['location_id'], item['directory_id'])
            if rpath is None:
                log('failed to get_library_path(section_id:%s, location_id:%s)' %(item['section_id'], item['location_id']))
                continue
            dest_root = get_dest_root(get_remote_path(rpath))
            if dest_root is None:
                #log('failed to dest_root: non-target(%s/%s' % (rpath, spath))
                continue

            # rclone move
            if RCLONE_FLAG:
                orig_path = os.path.join(get_remote_path(rpath), spath)
                dest_path = os.path.join(dest_root, spath)

                log('orig_path(%s)' % orig_path)
                log('dest_path(%s)' % dest_path)

                ret = move_ended_item(orig_path, dest_path)
                log(ret)
            # shutil.move
            else:
                orig_path = os.path.join(get_localpath_from_plexpath(rpath), spath)
                dest_path = os.path.join(get_local_path(dest_root), spath)

                log('orig_path(%s)' % orig_path)
                log('dest_path(%s)' % dest_path)
                if DRYRUN:
                    log('move %s %s' % (orig_path, dest_path))
                else:
                    shutil.move(orig_path, dest_path)

            #ret = move_ended_item(orig_path, dest_path)
            #log(ret)

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
