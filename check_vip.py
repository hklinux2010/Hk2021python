#auth: haokuo
# -*- coding: utf-8 -*- 
import os
import redis
import re
import sys
import logging
import logging.handlers
from optparse import OptionParser
reload(sys)
sys.setdefaultencoding('utf-8')
#VIP后面带的数字1代表在这个主机上0代表没有

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
#正则表达式的使用
def re_fun(re_pattern,result):
    compiled = re.compile(re_pattern,re.DOTALL)
    rets = compiled.findall(result)
    return rets
#获取所有的VIP
def get_h_vip():
    cmd="ip a|grep '/32'|awk -F '/32' '{print $1}'|awk '{print $2}'"
    h_vip=os.popen(cmd).read().split('\n')
    h_vip = [i for i in h_vip if i != '']
    return h_vip

#获取本机IP地址
def get_ip():
    cmd="for i in `find /etc/sysconfig/network-scripts/ -name 'ifcfg*'`;do  grep -i 'IPADDR' $i|grep '10.' ; if [ $(echo $?) -eq 0 ] ;then net=$(echo $i|echo $i|awk -F '-' '{print $NF}') ;if ip a|grep $net|grep -i 'UP';then grep -i 'IPADDR' $i|grep '10.'|awk -F '=' '{print $2}';fi ; fi ; done|tail -n 1"
    res=os.popen(cmd).read().split('\n')
    ip= [i for i in res if i != '']
    ip="".join(ip)
    return ip

#从配置文件中读取VIP
def get_f_vip(config):
    f_vip=[]
    with open(config,mode='r')as f:
        result=f.read()
    #re_pattern = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
    re_pattern = r'\s*virtual_ipaddress\s*\{(?P<address>.*?)\}'
    rets = re_fun(re_pattern,result)
    for ret in rets:
        f_vip.append(ret.replace(" ","").replace("\t","").replace("\r","").strip('\n'))
    return f_vip 
#判断VIP的类型
def check_vip_type(config):
     real_ip=[]
     re_pattern = r'\s*include\s*.*conf'
     with open(config,mode='r')as f:
        result=f.read()
     rets = re_fun(re_pattern,result)
     if rets:
         rets = rets[0].replace(" ","").replace("\n","").split('include')
     if rets:
         for i in rets:
             if i != '':
                 if os.path.exists(i):
                     with open(i,mode='r')as f:
                         result=f.read()
                     re_pattern = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
                     rets = re_fun(re_pattern,result)
                     for ip in list(set(rets)):
                         real_ip.append(ip)
                 else:
                     count="%s文件不存在"% i
                     logger.info(count)       
         return 1,list(set(real_ip))      
     else:
         return 3,4
#mha类型的
def mha_type():
     vip_status=[]
     cmd='find /etc/masterha/ -name "*init_vip.sh"'
     file_list=os.popen(cmd).read().split("\n")
     file_list = [i for i in file_list if i != '']
     for file in file_list:
         with open(file,mode='r')as f:
             result=f.read()
         re_pattern = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
         rets = re_fun(re_pattern,result)
         for ip in rets:
             cmd='ip a|grep %s'% ip
             if os.popen(cmd).read():
                 vip_status.append(ip+":1")
             else:
                 vip_status.append(ip+":0")
     return 2,vip_status          
#主函数     
def main(config):
     if os.path.exists(r'/etc/masterha/init_vip.sh'):
         vip_type,iplist=mha_type()
         data={
                   'type':'MHA',
                   'ipaddress': iplist
              }
     elif os.path.exists(config):
         vip_type,iplist= check_vip_type(config)
         if vip_type == 1:
             vip_status=[]
             h_vip=get_h_vip()
             f_vip=get_f_vip(config)
             for i in f_vip:
                 if i in h_vip:
                     vip_status.append(i+":1")
                 else:
                     vip_status.append(i+":0")
             data={
                   'type':'LVS',
                   'ipaddress': vip_status,
                   'real_server': iplist
                  }
         else:
             vip_status=[]
             h_vip=get_h_vip()
             f_vip=get_f_vip(config)
             for i in f_vip:
                 if i in h_vip:
                     vip_status.append(i+":1")
                 else:
                     vip_status.append(i+":0")
             data={
                   'type':'KEEPALIVED',
                   'ipaddress': vip_status
                  }
     else:
         data={}
     return data

if __name__ == '__main__':
     
    logger=logout(r'/data/logs/check_vip/check_vip.log')
    parser = OptionParser()
    parser.add_option('-c', '--config', type='string', dest='config',default='/etc/keepalived/keepalived.conf',help='\"KEEPALIVED config...\"')
    (options, args) = parser.parse_args()
    data = main(options.config)
    try:
        redis_conn=redis.ConnectionPool(host='10.33.125.177',port=9014)
        r = redis.StrictRedis(connection_pool=redis_conn)
        ip="{{inventory_hostname}}"
        r.hset("host:collected:vip:hash",ip,data)
        count="%s脚本执行成功！！"% ip
        logger.info(count)
    except BaseException as err:
        count="数据库写入失败！！%s" % err
        logger.error(count) 
        sys.exit(1)
   # r = redis.StrictRedis(connection_pool=redis_conn)
   # ip=get_ip()
   # r.hset("host:collected:vip:hash",ip,data)

