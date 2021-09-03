from pyzabbix import ZabbixAPI
import requests
import logging
import time
import logging
import logging.handlers
import os
import json
#监控的url地址
ZABBIX_SERVER = 'http://10.33.151.240:8099'
# 编写log日志
log_file=r'F:\work\zabbix\logs\stdout.txt'
#编写log日志
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
    logger.setLevel(logging.INFO)
    return logger
#从cmdb获取所有主机IP地址
def get_all_ip():
    count = 0
    iplist=[]
    url = "http://cmdb.svc.17paipai.cn/api/v1/asset/hosts/?page=1&page_size=4000&__t=1623069463698"
    headers = {
        'Content-Type': "application/json",
        'authorization': "Application f804bd5e-692f-11e8-a083-6805ca2f38d8",
    }
    while True:
        try:
            response = requests.request("GET", url, headers=headers)
            if int(response.status_code) == 200:
                break
            else:
                count += 1
                logging.info('Failed with one try, http response:%s' % response.text)
            if count >= 10:
                logging.info('Failed with max retry !. failed msg:')
                break
        except Exception as e:
            count += 1
            logging.info(e)
            if count >= 10:
                break
            else:
                pass
    dict1=response.json()
    for i in dict1.get('results'):
        iplist.append(i.get('ip'))
    return iplist
#获取所有状态为0的主机名称
def get_hostid():
    no_hostid=[]
    iplist=get_all_ip()
    hostids = {}
    with ZabbixAPI(ZABBIX_SERVER) as zapi:
        zapi.login('haokuo', 'haokuo')
        for ip in iplist:
            if ip.startswith("10") and not ip.startswith("10.101"):
                hosts = zapi.host.get(output=['name', 'status', 'hostid'], filter={'host': ip,'status': '0'})
                if hosts :
                    hostids[ip]=hosts[0].get('hostid')
                else:
                    no_hostid.append(ip)
        coment='在zabbix中被禁用的IP地址列表: ' + str(no_hostid)
    logger.info(coment)
    return hostids
#获取各个IP地址的监控项的itemid
def get_itemd():
    hostids = get_hostid()
    itemds = {}
    no_itemds=[]
    with ZabbixAPI(ZABBIX_SERVER) as zapi:
        zapi.login('haokuo', 'haokuo')
        for ip, hostid in hostids.items():
            result=zapi.item.get(output=["itemids"],hostids=hostid,search={"key_":"system.cpu.util[,system]"})
            if result:
                itemds[ip]=result[0].get('itemid')
            else:
                no_itemds.append(ip)
        coment = '在zabbix中没有监控项的IP地址列表:' + str(no_itemds)
        logger.info(coment)
    return itemds
#获取监控项的最新数据
def check_new_data():
    itemds = get_itemd()
    monior={}
    no_data=[]
    now_time=int(time.time())
    old_time=now_time - 600
    with ZabbixAPI(ZABBIX_SERVER) as zapi:
        zapi.login('haokuo', 'haokuo')
        for ip,itemd in itemds.items():
            data=zapi.history.get(history=0,limit=1, output='extend',itemids=itemd,time_from=old_time)
            if data:
                monior[ip]=data[0].get('value')
            else:
                no_data.append(ip)

        coment = '在zabbix中没有最新数据的IP地址列表：' + str(no_data)
        logger.info(coment)
    return no_data
if __name__ == '__main__':
    logger = logout(log_file)
    check_new_data()
