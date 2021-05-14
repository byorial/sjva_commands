# -*- coding: utf-8 -*-
 
import os, sys, subprocess, platform, socket
try:
    from discord_webhook import DiscordWebhook, DiscordEmbed
except ImportError:
    if sys.version_info[0] == 2:
        os.system('pip install discord_webhook')
    else:
        os.system('pip3 install discord_webhook')

    from discord_webhook import DiscordWebhook, DiscordEmbed
 
 
# global vars..
PLATFORM = platform.system()
 
 
# basic set for discord webhook
STATUS  = "status"
WARNING = "warning"
 
 
WEBHOOKS = { 
        STATUS:"https://discord.com/api/webhooks/...상태알림받을웹훅주소", 
        WARNING:"https://discord.com/api/webhooks/...경고알림받을웹훅주소" 
        }

COLORS = { STATUS: 242424, WARNING: 16711680 }
WHLIST = dict()
SVR_NAME = socket.gethostname().upper()     # 서버 명 직접입력 가능
#SVR_NAME = "서버명"
#WATCH_PATH = ['C:', 'P:', 'X:'] # 감시할 경로 입력:윈도우
WATCH_PATH = ['/dev/sda1', '/mnt/gdrive'] # 감시할 경로 입력: 리눅스 dev명 또는 경로명 적절히 입력
DISK_ALARM_LIMIT = "75"   # 경고알람 기준
TITLES = {
        STATUS :"[알림] ({svr})서버 파일시스템 사용량 정보 (기준: {limit}%)".format(svr=SVR_NAME, limit=DISK_ALARM_LIMIT),
        WARNING:"[경고] ({svr})서버 파일시스템 사용량 경보 (기준: {limit}%)".format(svr=SVR_NAME, limit=DISK_ALARM_LIMIT)
        }
 
 
MSG_QUEUE = { STATUS: [], WARNING: [] }
 
 
def init_discord_webhook():
    for whkey in WEBHOOKS.keys():
        wh  = DiscordWebhook(url=WEBHOOKS[whkey])
        WHLIST[whkey] = [wh, 0]
 

def get_discord_webhook(whkey):
    return WHLIST[whkey]
 
 
def send_discord_msg():
    for whkey in WEBHOOKS.keys():
        mqueue = MSG_QUEUE[whkey]
        if len(mqueue) == 0: continue
        
        wh = get_discord_webhook(whkey)
        embed = DiscordEmbed(title=TITLES[whkey], color=COLORS[whkey])
        embed.set_author(name=SVR_NAME)
     
        path = "\n".join([x[0] for x in mqueue])
        used = "\n".join([x[2]+"/"+x[1] for x in mqueue])
        usep = "\n".join([x[3] for x in mqueue])
        
        embed.add_embed_field(name="경로", value=path, inline=True)
        embed.add_embed_field(name="사용/전체", value=used, inline=True)
        embed.add_embed_field(name="사용률", value=usep, inline=True)

        embed.set_timestamp()
        wh[0].add_embed(embed)
        response = wh[0].execute()
        print (response)
 
 
 
def is_limit_over(usep):
    nusep = int(usep.replace('%', ''))
    return (nusep > int(DISK_ALARM_LIMIT))
 
 
def check_disk_usage_linux():
    #cmd 
    cmd_df = os.popen('which df').read().split('\n')[0].strip()
    cmd_egrep = os.popen('which egrep').read().split('\n')[0].strip()
    str_egrep = "|".join(WATCH_PATH)
    cmd = '{df} -h | {grep} "{gstr}"'.format(df = cmd_df, grep = cmd_egrep, gstr=str_egrep)
 
    #for line in subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).split('\n'):
    for line in os.popen(cmd).read().split('\n'):
        if line == '': continue
        data = line.split()
        fs  = data[5] ####### 1: 마운트dev 기준, 5: 경로기준
        total = data[1]
        use = data[2]
        usep= data[4]
 
        if is_limit_over(usep): whtype = WARNING
        else: whtype = STATUS
        MSG_QUEUE[whtype].append([fs, total, use, usep])
 
 
 
def check_disk_usage_windows():
    cmd = 'wmic logicaldisk get deviceid,size,freespace'.split()
 
 
    for line in subprocess.check_output(cmd).decode('utf-8').split('\r\n'):
        if line.startswith('rn'): continue
        try:
            data = line.split()
            if data[0] not in WATCH_PATH: continue
            nfr = float(data[1]) / (1024 * 1024 * 1024)
            nto = float(data[2]) / (1024 * 1024 * 1024)
            nus = nto - nfr
 
 
            fs      = data[0]
            total   = str(int(nto)) + "G"
            use     = str(int(nto-nfr)) + "G"
            usep    = str(int(nus/nto*100)) + "%"
 
 
            if is_limit_over(usep): whtype=WARNING
            else: whtype = STATUS
 
            MSG_QUEUE[whtype].append([fs, total, use, usep])
        except:
            print ("Exception accured: ignored")
 
 
def check_disk_usage():
    if PLATFORM == 'Windows': check_disk_usage_windows()
    else: check_disk_usage_linux()
 
 
# MAIN
init_discord_webhook()
check_disk_usage()
send_discord_msg()
