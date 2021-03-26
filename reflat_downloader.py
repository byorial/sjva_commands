# -*- coding: utf-8 -*-
import sys
if __name__== "__main__":
    reload(sys)
    sys.setdefaultencoding('utf-8')
import os, traceback
logger = None
########################################################################## 이 위 고정
import requests
import glob, guessit
import urllib
import shutil
from lxml import html
import re

try:
    import chardet
except ImportError:
    os.system('pip install chardet')
    import chardet

try:
    from langdetect import detect
except ImportError:
    os.system('pip install langdetect')
    from langdetect import detect

#####################################################################################
# 사용자 설정값
#####################################################################################
# source - 자막없는 영상들이 들어있는 경로: 하위폴더까지검색, 
# dest - 자막을 찾은 경우 이동할 경로
target_list = [
        {'source':'/opt/test/sub_x', 'dest':'/opt/test/sub_o'},
        ]

# 검색어 기준 설정 - 순서대로 적용: guessit key 지원하나 적절한 검색어 설정 필요
# 지원값: title, year, screen_size, release_group, source, video_codec, container, mimetype, type
search_rules = [
        ['title', 'year', 'screen_size', 'release_group'],      # 1. 제목, 년도, 해상도, 릴그룹으로 조회
        ['title', 'year', 'release_group'],                     # 2. 제목, 년도, 릴그룹으로 조회
        ['title', 'year']                                       # 3. 제목, 년도로 조회
        ]
# 자막파일을 다운받을 임시 경로: *로컬경로*로 지정, 미지정시 영상폴더로 다운(Remote의 경우 가급적 지정해주세요)
tmp_sub_path = '/tmp/subs'
# dry_run: True: 자막다운 O, 파일이동 X, False: 자막다운 O, 파일이동 O
dry_run = True
# 원본 폴더명 유지 
use_orig_dname = True
# 자막파일을 다운받은 경우 이동시 target 경로에 폴더를 만들지 여부 
create_dir = True
# 자막파일을 다운받은 경우 이동시 폴더명규칙: guessit key 지원하나 적절히 설정필요(에러발생시 '제목 (년도)'로 생성)
dir_format = '{title} ({year})'     # '제목 (연도)'
# 자막파일 언어체크: True - 영어자막은 스킵함
korsub_only = True
# 인코딩 오류 파일 예외처리 대상 언어 목록 지정
except_langs = ['ca']
# 영상파일 이동후 원래 폴더가 비어있는 경우 삭제여부: 영화가 폴더안에 있는경우만 해당함
remove_empty_dir = True

#####################################################################################
def is_video(fpath):
    video_exts = ['.mp4', '.mkv', '.avi', '.wmv', '.flv']
    if os.path.isdir(fpath): return False
    if os.path.splitext(fpath)[1] in video_exts:
        if not is_exist_sub(fpath):
            return True
    return False

def is_exist_sub(fpath):
    sub_exts = ['.ko.srt', '.srt', '.smi', '.ko.smi', '.kor.srt', '.ass', '.ko.ass']
    for ext in sub_exts: 
        spath = os.path.splitext(fpath)[0] + ext
        if os.path.isfile(spath):
            log(u'[SKIP] 자막파일 있음: 경로(%s)' % spath)
            return True
    return False

def load_videos(target_path):
    file_list = []
    if not os.path.isdir(target_path):
        log(u'대상 폴더가 존재하지 않음:{f}'.format(f=target_path))
    for (path, dir, files) in os.walk(target_path):
        for filename in files:
            if is_video(os.path.join(path,filename)):
                file_list.append(os.path.join(path, filename))

    return file_list

def get_sub_list(keyword):
    search_url  = 'https://reflat.net/sear/{keyword}?'
    qstr = urllib.quote(keyword.encode('utf-8'))
    url = search_url.format(keyword=qstr)

    #TODO: exception handling
    r = requests.get(url)
    if r.status_code != 200:
        log(u'자막파일 검색실패: status_code({c})'.format(c=r.status_code))
        return None

    tree = html.fromstring(r.content)
    subs = tree.xpath("//div[@class='card-body']/h4/a")
    sub_list = []
    for sub in subs:
        # TODO: 자막 선택 조건 적용
        #log(sub.get('href'))
        sub_url = sub.get('href')
        from urlparse import urlparse, parse_qsl
        parts = urlparse(sub_url)
        qs = dict(parse_qsl(parts.query))
        sub_seq = qs['seq']
        sub_list.append(sub_seq)
    
    return sub_list

def get_texts(xmldata):
    import re
    texts = []
    for line in xmldata.split('\n'):
        text = re.sub(r"\<[^()]*\>", u'', line)
        text = re.sub(r"&nbsp;",u' ',text)
        if text != "": texts.append(text)

    return u'\n'.join(texts)
    #root = html.fromstring(xmldata)
    #return root.text_content()

def conv_encoding(data, new_coding='UTF-8'):
    coding = chardet.detect(data)['encoding']
    log("coding: "+coding)
    if new_coding.upper() != coding.upper():
        data = unicode(data, coding).encode(new_coding)
    return data

def download_sub(sub_seq, video_path):
    global tmp_sub_path, korsub_only, except_langs

    sub_url    = 'https://reflat.net/loadFILES?p_seq={sub_seq}'
    down_url   = 'https://sail.reflat.net/api/dwFunc/?l=blog%2F{owner}%2F{floc}&f={title}'
    url = sub_url.format(sub_seq=sub_seq)
    r = requests.get(url)
    if r.status_code != 200:
        log(u'자막파일 확인 실패: url(%s)' % url)
        return None

    dname = os.path.dirname(video_path)
    name  = os.path.splitext(os.path.basename(video_path))[0]
    tree  = html.fromstring(r.content)
    subs  = tree.xpath("//a")

    found = False
    for sub in subs:
        title = sub.get('title').strip()
        owner = sub.get('data-owner').strip()
        floc = sub.get('data-floc').strip()

        ext = os.path.splitext(title)[1]
        if ext.lower() not in [u'.srt', u'.smi']:
            continue

        found = True
        surl = down_url.format(owner=owner, floc=floc, title=urllib.quote(title.encode('utf-8')))
        if tmp_sub_path != '' and os.path.isdir(tmp_sub_path):
            spath = os.path.join(tmp_sub_path, name + ext)
        else:
            spath = os.path.join(dname, name + ext)
        break

    if not found:
        log(u'자막파일 확인실패: url(%s)' % url)
        return None

    if os.path.isfile(spath):
        log(u'자막파일이 이미 존재합니다.(%s)' % (spath))
        return spath

    log(u'자막파일 다운시도: url(%s)' % (surl))
    headers = { 'Accept': 'text/html, */*; q=0.01','User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36'}
    r = requests.get(surl, headers=headers)
    if r.status_code != 200:
        log(u'자막파일 다운실패: url(%s), code(%d)' % surl, r.status_code)
        return None

    content = r.content
    text = r.text
    if content.upper().find('</SAMI>') != -1:
        content = content[:content.upper().find('</SAMI>')+len('</SAMI>')]
    if text.upper().find('</SAMI>') != -1:
        text = text[:text.upper().find('</SAMI>')+len('</SAMI>')]

    if ext == '.smi': texts = get_texts(text)
    #log(texts)
    lang = detect(texts)
    cd = chardet.detect(bytes(texts))
    encoding = cd['encoding']
    log('자막파일 언어정보: encoding(%s), lang(%s), confidence(%.2f)' % (cd['encoding'], lang, cd['confidence']))
    if korsub_only:
        if lang != u'ko':
            if lang in except_langs:
                log(u'자막파일 예외처리: 인코딩 강제변환')
                texts = unicode(content, 'EUC-KR').encode('utf-8')
            else:
                log(u'자막파일 스킵처리: 한글자막아님, 언어(%s)' % (lang))
                return None

    f = open(spath, mode='wb')
    try:
        if lang in except_langs: size = f.write(texts)
        elif encoding != None: size = f.write(content.decode(encoding).encode('utf-8'))
        else: size = f.write(text.encode('utf-8'))
    except UnicodeDecodeError, AttributeError:
        size = f.write(text.encode('utf-8'))
    f.close()
    return spath

def log_git(git):
    try:
        log(u'영화파일 정보확인: 제목(%s), 년도(%s), 릴그룹(%s)' % (git['title'], git['year'], git['release_group']))
    except:
        try: log(u'영화파일 정보확인: 제목(%s), 년도(%s)' % (git['title'], git['year']))
        except: log(u'영화파일 정보확인: 제목(%s)' % (git['title']))

def is_empty_dir(dpath):
    import scandir
    return not any ([True for _ in scandir.scandir(dpath)])

def run(args):
    global target_list, search_rules, create_dir, dir_format, use_orig_dname
    try:
        for target in target_list:
            vlist = load_videos(target['source'])
            for f in vlist:
                log('-----------------------------------------------------------------------------')
                found = False
                log(u'자막파일 검색시도: 파일명(%s)' % f)
                git = guessit.guessit(f)
                log_git(git)
                for rule in search_rules:
                    try:
                        klist = [unicode(git[key]) for key in rule]
                    except KeyError:
                        continue
                    keyword = u' '.join(klist)
                    sub_list = get_sub_list(keyword)
                    if sub_list is None:
                        log(u'자막파일 검색실패: 검색어(%s)' % (keyword))
                        continue
                    if len(sub_list) == 0: continue
                    log(u'자막파일 검색완료: 검색어(%s), 검색결과수(%d)' % (keyword, len(sub_list)))
                    found = True
                    break

                if not found:
                    log(u'자막파일 검색실패: 파일명(%s)' % f)
                    continue

                download = False
                for sub_seq in sub_list:
                    sub_path = download_sub(sub_seq, f)
                    if sub_path is None:
                        log(u'자막파일 다운실패: 파일명(%s), 자막SEQ(%s)' % (f, sub_seq))
                        continue

                    download = True
                    log(u'자막파일 다운완료: 파일명(%s)' % sub_path)
                    source_dir = target['source']
                    target_dir = target['dest']
                    break

                if not download:
                    log(u'자막파일 다운실패: 파일명(%s)' % f)
                    continue

                if create_dir:
                    try:
                        tdir_name = dir_format.format(
                                title=git['title'],
                                year=git['year'],
                                screen_size=git['screen_size'],
                                source=git['source'],
                                release_group=git['release_group'],
                                video_codec=git['video_codec'],
                                type=git['type'])
                        target_dir = os.path.join(target_dir, tdir_name)
                    except KeyError:
                        if 'year' in git: tdir_name = '{title} ({year})'.format(title=git['title'], year=git['year'])
                        else: tdir_name = git['title']
                        target_dir = os.path.join(target_dir, tdir_name)
 
                if use_orig_dname:
                    source_dir = os.path.dirname(f)
                    orig_dname = os.path.basename(source_dir)
                    if source_dir != target['source']:
                        target_dir = os.path.join(target['dest'], orig_dname)
    
                if dry_run:
                    log('[DRYRUN] move %s to %s' % (f, target_dir))
                    log('[DRYRUN] move %s to %s' % (sub_path, target_dir))
                # move
                else:
                    if not os.path.isdir(target_dir): os.makedirs(target_dir)
                    tfname = os.path.join(target_dir, os.path.basename(f))
                    if os.path.isfile(tfname):
                        log(u'[SKIP] 이동대상경로에 동일파일이 존재합니다.(경로:%s)' % tfname)
                    else:
                        log(u'영상파일 이동처리: move %s to %s' % (f, target_dir))
                        shutil.move(f, target_dir)

                    tsname = os.path.join(target_dir, os.path.basename(sub_path))
                    if os.path.isfile(tsname):
                        log(u'[SKIP] 이동대상경로에 동일파일이 존재합니다.(경로:%s)' % tsname)
                    else:
                        log(u'자막파일 이동처리: move %s to %s' % (sub_path, target_dir))
                        shutil.move(sub_path, target_dir)

                    if remove_empty_dir:
                        dpath = os.path.dirname(f)
                        if os.path.isdir(dpath) and is_empty_dir(dpath) and dpath != target['source']:
                            log(u'원본영상 폴더삭제: 경로(%s)' % dpath)
                            os.rmdir(dpath)
    
        log('-----------------------------------------------------------------------------')
    except Exception as e:
        log('Exception %s', e)
        log(traceback.format_exc())

##########################################################################
# 파일 실행방식 & LOAD 방식 겸용
##########################################################################
def main(*args, **kwargs):
    global logger
    if 'logger' in kwargs:
        logger = kwargs['logger']
    log('=========== SCRIPT START ===========')
    run(args)
    log('=========== SCRIPT END ===========')

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

if __name__== "__main__":
    main()
