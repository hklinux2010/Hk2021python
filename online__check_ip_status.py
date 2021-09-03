from pyzabbix import ZabbixAPI
import logging
import logging.handlers
import os
import time
import traceback
import subprocess
import requests
# 监控的url地址
ZABBIX_SERVER = 'http://10.33.151.240:8099'
#配置文件地址
CONFIG_DIR = r'/opt/zabbix/ip.txt'
# 获取所有状态为1的主机名称
def get_ip():
    hostname = []
    with ZabbixAPI(ZABBIX_SERVER) as zapi:
        zapi.login('haokuo', 'haokuo')
        hosts = zapi.host.get(output=['name', 'status'], selectInterfaces=['ip'], filter={'status': '1'})
        for host in hosts:
            if host['interfaces'][0].get('ip') != '':
                hostname.append(host['interfaces'][0].get('ip'))
        print(hostname)

# 检测IP地址是否存在
def check_network():
    iplist = get_ip()
    no_list = []
    for ip in iplist:
        cmd = "ping -w 2 -c 4 -i 0.2 {0}".format(ip)
        print(cmd)
        re_status = subprocess.call(cmd, shell=True, stdout=subprocess.PIPE)
        if re_status == 0:
            no_list.append(ip)
    return no_list

# 编写log日志
def logout(logfile):
    """
    按天切割日志
    """
    if not os.path.exists(os.path.dirname(logfile)):
        os.makedirs(os.path.dirname(logfile))
    logger = logging.getLogger()
    hdlr = logging.handlers.TimedRotatingFileHandler(logfile, when='midnight', backupCount=0)
    hdlr.suffix = '%Y-%m-%d'
    formatter = logging.Formatter('%(levelname)s %(asctime)s [%(filename)s:%(lineno)d]: %(message)s')
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr)
    logger.setLevel(logging.NOTSET)
    return logger

#发送告警信息
def send_msg(content):
    """
    发送告警信息
    """
    url = "http://xalert.pub.17paipai.cn/api/v1/alarms/general/"
    payload = {
        "app": "smart-pika-write-monitor",
        "type": "check",
        "host_name": "",
        "severity": "4",
        "content": content,
        "receiver": "郝阔"
    }
    headers = {
        "Content-Type": "application/json",
        "authorization": "Application 8d923df6-01dd-11e9-ad73-6805ca2f33bc",
    }
    for i in range(3):
        try:
            response = requests.request("POST", url, json=payload, headers=headers)
            if response.status_code == 200:
                return True
            else:
                logger.info("%s %s" % (url, response.status_code))
        except:
            logger.info(url)
            logger.info(traceback.format_exc())
        time.sleep(1)
    return False

#过滤白名单
def check_write():
    iplist = check_network()
#存储过滤好的IP地址
    f_iplist=[]
    with open(CONFIG_DIR, 'r')as r:
        result = r.read()
    for ip in iplist:
        if ip not in result:
            f_iplist.append(ip)
    return f_iplist

if __name__ == '__main__':
    result=check_write()
    text = ","
    content = text.join(result) + "监控禁用状态,主机在使用中"
    logger = logout("/data/logs/zabbix/zabbix_check_ip_status.log")
    logger.info(content)
    send_msg(content)

