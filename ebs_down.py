# -*- coding: utf-8 -*-
#!/usr/bin/env python
# python 3로 해야함~ 

logger = None
import os, traceback
import shutil
import re
import requests
from urllib.request import urlretrieve as Retrieve
import json
import progressbar

try:
    from bs4 import BeautifulSoup
except ImportError as e:
    os.system('pip install bs4')
    from bs4 import BeautifulSoup

###############################################################################
# user setting
###############################################################################
# 다운받을 에피소드
start_ep = 100    # 시작에피번호
end_ep = 101      # 종료에피번호, 0: 지정시 전체(최대에피소드: 697)
down_dir = '/tmp/명의'
fname_format = u'명의.E{ep}.{date}.1080p-EBS.mp4'
#fname_format = u'명의.E{ep}.{title}.{date}.1080p-EBS.mp4'
###############################################################################
# global vars..
###############################################################################
BASEURL = 'https://bestdoctors.ebs.co.kr/bestdoctors/etc/vodCommon/getLectList'
MAX_RETRY = 3
pbar = None
###############################################################################

def get_all_list(url):
    for i in range(1, MAX_RETRY + 1):
        try:
            headers = { 'Accept': 'text/html, */*; q=0.01','Connection': 'keep-alive', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Host': 'bestdoctors.ebs.co.kr', 'Origin': 'https://:bestdoctors.ebs.co.kr', 'Referer': 'https://bestdoctors.ebs.co.kr/bestdoctors/vodReplayView?siteCd=ME&courseId=BP0PAPG0000000014&stepId=01BP0PAPG0000000014&lectId=20470649', 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36', 'X-Requested-With': 'XMLHttpRequest'} 
            post_data = {'siteCd':'ME',
                    'courseId':'BP0PAPG0000000014',
                    'stepId':'01BP0PAPG0000000014',
                    'lectId':'20470649',
                    'pageNum':'1',
                    'hmpId':'bestdoctors',
                    'nowLectId':'20470649',
                    'pageSize':'900'}
            r = requests.post(url, data=post_data, headers=headers)
            if r.status_code == 200 and len(r.text) > 1024: break
        except:
            log('error accured(url:%s)' % url)
            return None

    if i == MAX_RETRY:
        log('failed to get response(url:%s)' % url)
        return None

    return r

def get_item(cid, sid, lid):
    for i in range(1, MAX_RETRY + 1):
        try:
            url = 'https://bestdoctors.ebs.co.kr/bestdoctors/vodReplayView?siteCd=ME&courseId={}&stepId={}&lectId={}'.format(cid,sid,lid)
            headers = { 'Accept': 'text/html, */*; q=0.01','Connection': 'keep-alive', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Host': 'bestdoctors.ebs.co.kr', 'Origin': 'https://:bestdoctors.ebs.co.kr', 'Referer': 'https://bestdoctors.ebs.co.kr/bestdoctors/vodReplayView?siteCd=ME&courseId=BP0PAPG0000000014&stepId=01BP0PAPG0000000014&lectId=20470649', 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36', 'X-Requested-With': 'XMLHttpRequest'} 
            r = requests.post(url, headers=headers)
            if r.status_code == 200 and len(r.text) > 1024: break
        except:
            log('error accured(url:%s)' % url)
            return None

    if i == MAX_RETRY:
        log('failed to get response(url:%s)' % url)
        return None

    return r


def get_param(url):
    for p in url.split('&'):
        if p.startswith('courseId='): courseId = p.split('=')[1]
        if p.startswith('stepId='): stepId = p.split('=')[1]
        if p.startswith('lectId='): lectId = p.split('=')[1]
    return courseId, stepId, lectId

def get_video_url(cid, sid, lid):
    r = get_item(cid, sid, lid)
    soup = BeautifulSoup(r.text, "html.parser")
    scripts = soup.findAll('script')
    for script in scripts:
        # 1080p url 찾기
        if script.string == None: continue
        if script.string.find('source = [') == -1: continue
        p = re.compile(r"{code: 'M50',.+\ssrc: '(?P<url>https://.+)['].+}")
        match = p.search(script.string)
        if match:
            url = match.group('url')
            return url
    return None

def show_progress(block_num, block_size, total_size):
    global pbar
    if pbar is None:
        pbar = progressbar.ProgressBar(maxval=total_size)
        pbar.start()

    downloaded = block_num * block_size
    if downloaded < total_size:
        pbar.update(downloaded)
    else:
        pbar.finish()
        pbar = None

def run(args):
    global BASEURL, start_ep, end_ep, fname_format, down_dir
    r = get_all_list(BASEURL)
    soup = BeautifulSoup(r.text, "html.parser")
    vods = soup.find_all('div', {'class':'pro_vod'})
    vod_list = []
    i = 0
    for vod in vods:
        cid, sid, lid = get_param(vod.p.a['href'])
        title = vod.p.a['title']
        yymmdd = vod.p.span.text.replace('.','')[2:]
        vod_list.append({'cid':cid, 'sid':sid, 'lid':lid, 'title':title, 'date':yymmdd})
    
    if start_ep <= 0: start_ep = 1
    if end_ep == 0 or end_ep > len(vod_list): end_ep = len(vod_list)
    if start_ep > end_ep: start_ep = end_ep

    vod_list.reverse() # ep순 정렬

    log(u'-----------------------------------------------------')
    log(u'전체  에피소드 수: %d' % len(vod_list))
    log(u'다운대상 에피소드: %d - %d' % (start_ep, end_ep))
    log(u'-----------------------------------------------------')

    if not os.path.isdir(down_dir): os.makedirs(down_dir)

    curr = 1
    total = end_ep - start_ep + 1
    for (ep,vod) in enumerate(vod_list, start=1):
        if ep < start_ep or ep > end_ep: continue
        video_url = get_video_url(vod['cid'], vod['sid'], vod['lid'])
        if video_url == None:
            log('failed to get video_url: {},{},{}'.format(vod['cid'], vod['sid'], vod['lid']))
            continue
        log('[curr/total: %d/%d]' % (curr, total))
        log('episode: {0:03d}'.format(ep))
        epstr = '{0:03d}'.format(ep)
        log('title  : '+vod['title'])
        log('date   : '+vod['date'])
        log('url    : '+video_url)
        fname = fname_format.format(ep=epstr,date=vod['date'],title=vod['title'])
        fpath = os.path.join(down_dir, fname)
        log('path   : '+fpath)
        Retrieve(video_url, fpath, show_progress)
        curr += 1

def log(*args):
    global logger
    try:
        if logger is not None:
            logger.debug(*args)
        if len(args) > 1:
            print(args[0] % tuple([str(x) for x in args[1:]]))
        else:
            print(str(args[0]))
        #sys.stdout.flush()
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
