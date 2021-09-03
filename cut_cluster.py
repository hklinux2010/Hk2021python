# -*- coding: utf-8 -*-
import redis
import re
import time
import sys
import os
import yaml
import requests
import traceback
import subprocess
from optparse import OptionParser
reload(sys)
sys.setdefaultencoding('utf-8')

def initlog(logpath):
    logging.basicConfig(filename=logpath, level=logging.INFO, format='%(asctime)s:%(levelname)s:%(message)s')


loggers = {}
def get_logger(logfile):
    import logging
    import logging.handlers
    if not os.path.exists(os.path.dirname(logfile)):
        os.makedirs(os.path.dirname(logfile))
    global loggers
    logger = logging.getLogger()
    hdlr = logging.handlers.TimedRotatingFileHandler(logfile,when='midnight',backupCount=0)
    hdlr.suffix = '%Y-%m-%d'
    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr)
    logger.setLevel(logging.NOTSET)
    return logger


#读取配置文件
def get_configfile():
    parser = OptionParser()
    parser.add_option("-c", "--config", dest="config", help="smart cluster config file...", metavar="CONFIG")

    (options, args) = parser.parse_args()

    if options.config and os.path.isfile(options.config):
        return options.config
    else:
        print ("Please use < python smart_ha.py -h > see Usage method.........")
        exit(1)
#摘除失败
def exit_smart_ha_script(*args):
    prinrt ("smart分片摘除换失败,请马上检查...")
    exit(1)


#检测ip的状态
def check_network(ip):
    cmd = "ping -w {0} -c 4 -i 0.2 {1}".format(deadline, ip)
    for i in range(3):
        try:
            re_status = subprocess.call(cmd, shell=True, stdout=subprocess.PIPE)
            if re_status == 0:
                return True
            else:
                logger.info("Host {0} there is a problem with the network".format(ip))
        except Exception as err:
            logger.info("Network ping check is failed......\n %s" % err)
        time.sleep(1)
    return False

#创建redis连接的类
class Opredis(object):
    def __init__(self,*args,**kwargs):
        self._redishost = kwargs.get("host")
        self._redisport = kwargs.get("port")
        try:
            pool = redis.ConnectionPool(host=str(self._redishost), port=int(self._redisport))
            self.r = redis.Redis(connection_pool=pool)
        except:
            logging.error('{0}:{1} unreachable'.format(self._redishost,self._redisport))

    def ping(self):
        try:
            return self.r.ping()
        except:
            return False

    def reidisConnect(self):
        return self.r

#摘除down的smart-server和smart-proxy
def drop_down_smart_server(down_ip):
#设置两个列表
    down_host_ip_list, working_host_ip_list = [], []
    for s_line in all_smart_info:
        host_ip = s_line.replace(' ','').split('|')[5]
        if host_ip == down_ip:
            down_host_ip_list.append(s_line)
        elif host_ip != down_ip:
            working_host_ip_list.append(s_line)

    for p_line in all_proxy_info:
        host_ip, host_port = p_line.replace(' ','').split('|')[3], p_line.replace(' ','').split('|')[4]
        if host_ip == down_ip:
            r.execute_command("delproxy {0} {1}".format(host_ip, host_port))
            logger.info("delproxy {0} {1}".format(host_ip, host_port))

    time.sleep(3)

    down_host_ip_list.sort()
    working_host_ip_list.sort() 

    if len(down_host_ip_list):
        init_num = -1
        down_smart_id = []
        for down_smart in down_host_ip_list:
            #宕掉机器的smart的id
            down_id = int(down_smart.replace(' ','').split('|')[1])
            # 宕掉机器的smart的index
            down_index = int(down_smart.replace(' ','').split('|')[2])
            #取工作的最后一个分片的id和index
            working_id = int(working_host_ip_list[init_num].replace(' ','').split('|')[1])
            working_index = int(working_host_ip_list[init_num].replace(' ','').split('|')[2])
            if down_id < working_id:
                try:
                    #删掉宕机的分片
                    r.execute_command("delconfig {0}".format(down_id))
                    logger.info("delconfig {0}".format(down_id))
                    #删除工作的分片
                    r.execute_command("delconfig {0}".format(working_id))
                    logger.info("delconfig {0}".format(working_id))
                    #添加工作的分片
                    r.execute_command("addconfig {0} {1}".format(down_id, working_index))
                    logger.info("addconfig {0} {1}".format(down_id, working_index))
                    time.sleep(2)
                    init_num = init_num - 1
                except:
                    logger.info(traceback.format_exc())
                    exit_smart_ha_script()
            else:
                try:
                    #删除config配置
                    r.execute_command("delconfig {0}".format(down_id))
                    logger.info("delconfig {0}".format(down_id))
                except:
                    logger.info(traceback.format_exc())
                    exit_smart_ha_script()
            down_smart_id.append(down_index)
        time.sleep(2)
        try:
            #应用同步
            r.execute_command("apply force")
            logger.info("apply force")
        except:
            logger.info(traceback.format_exc())
            exit_smart_ha_script()
        time.sleep(10)
        for down_id in down_smart_id:
            try:
                #删除smart分片
                r.execute_command("delsmart {0}".format(down_id))
                logger.info("delsmart {0}".format(down_id))
            except:
                logger.info(traceback.format_exc())
                exit_smart_ha_script()
        monitor_info = " {0} ... {1}".format(smart_cluster, down_ip)
        print (" smart server 故障分片摘除成功..")

if __name__ == "__main__":
    deadline = 2
    config = yaml.load(open(get_configfile()), Loader=yaml.FullLoader)
    logfile = config["logpath"]
    logger = get_logger(logfile)
    center_addr, center_port = config["center_addr"], config["center_port"]
    smart_cluster = "{0}:{1}".format(config["center_addr"],config["center_port"])
    lock_redis_addr, lock_redis_port = config["lock_redis_addr"], config["lock_redis_port"]
    r = Opredis(host=center_addr,port=center_port).reidisConnect()
    rw = Opredis(host=lock_redis_addr, port=lock_redis_port).reidisConnect()

    while True:
        switch_lock = rw.get("smart:cluster:{0}:lock:string".format(center_port))

        if switch_lock == 0 or switch_lock == None: 
            smart_result = r.execute_command('info config')
            proxy_result = r.execute_command('info proxy')
            all_smart_info = re.findall('\|\s+\d+.*', smart_result.split('# PRECONFIG')[0], re.MULTILINE)
            pre_smart_info = re.findall('\|\s+\d+.*', smart_result.split('# PRECONFIG')[1], re.MULTILINE)
            all_proxy_info = re.findall('\|\s+\d+.*', proxy_result, re.MULTILINE)
            cluster_host_ip = set()

            if all_smart_info == pre_smart_info:
                pass
            else:
                print("smart cluster 线上配置和预配置不同,请检查后重启smart-ha ...")
                exit(1)
 
            for s_line in all_smart_info:
                cluster_host_ip.add(s_line.replace(' ','').split('|')[5])

            for ip in cluster_host_ip:
                status = check_network(ip)
                if not status:
                    drop_down_smart_server(ip)
                    rw.set("smart:cluster:{0}:lock:string".format(center_port), 1)
                else:
                   logger.info("Cluster normal.....")
        else:
            logger.info("Cluster has been switched, please clean redis key")

        time.sleep(15)


