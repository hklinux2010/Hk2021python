
# -*- coding:utf-8 -*-
import os,sys,time
import redis
import re
import json
import logging
import requests
import traceback
import subprocess

def get_logger(logfile):
    import logging
    import logging.handlers
    if not os.path.exists(os.path.dirname(logfile)):
        os.makedirs(os.path.dirname(logfile))
    logger = logging.getLogger()
    hdlr = logging.handlers.TimedRotatingFileHandler(logfile,when='midnight',backupCount=0)
    hdlr.suffix = '%Y-%m-%d'
    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr)
    logger.setLevel(logging.NOTSET)
    return logger

# 连接redis地址函数
def connRedis(redishost,redisport,logger):
    pool = redis.ConnectionPool(host=str(redishost), port=int(redisport))
    r = redis.Redis(connection_pool=pool)
    try:
        r.ping()
        return r
    except:
        print("{0}:{1}".format(redishost, redisport))
        print(traceback.format_exc())

# 获取集群中分片使用服务器IP
def get_cluster_host_ip(*args):
    result = dashboard_json_data["stats"]["group"]
    for line in result["models"]:
        for server in line["servers"]:
            r.sadd("codis:cluster:{0}:host:ip:set".format(dashboard_port), str(server["server"]).split(":")[0])

# 获取集群中每组主从信息并写入到redis
def get_cluster_group_info(*args):
    result = dashboard_json_data["stats"]["group"]
    for line in result["models"]:
        gid = line["id"]
        group_info = {}
        for group in line["servers"]:
            addr, port = tuple(group["server"].split(":"))
            try:
                role = connRedis(addr,port,logger).info()["role"]
                if role == "master":
                    group_info["master"] = group["server"]
                elif role == "slave":
                    group_info["slave"] = group["server"]
            except:
                logging.error(traceback.format_exc())
        r.hset("codis:cluster:{0}:group:hash".format(dashboard_port), gid, json.dumps(group_info))

# 获取集群中所有codis-proxy代理并写入到redis
def get_cluster_proxy_info(*args):
    result = dashboard_json_data["stats"]["proxy"]
    for line in result["models"]:
        r.sadd("codis:cluster:{0}:proxy:set".format(dashboard_port), line["admin_addr"])

# 检测集群中分片所在机器的存活状态
def check_network(ip):
    cmd = "ping -w {0} -c 4 -i 0.2 {1}".format(wait, ip)
    for i in range(3):
        try:
            re_status = subprocess.call(cmd, shell=True, stdout=subprocess.PIPE)
            if re_status == 0:
                print("{0} is ok!!!".format(ip))
                return True
        except Exception as err:
            print("Network ping check is failed......\n {0}".format(err))
        time.sleep(1)
    return False

# 清理redis里集群信息数据
def init_redis(dashboard_port):
    r.delete("codis:cluster:{0}:group:hash".format(dashboard_port))
    r.delete("codis:cluster:{0}:lock:string".format(dashboard_port))
    r.delete("codis:cluster:{0}:host:ip:set".format(dashboard_port))
    r.delete("codis:cluster:{0}:proxy:set".format(dashboard_port))

# 删除集群中故障机器上的codis-proxy代理
def remove_proxy(dashboard, p_addr):
    command = "/usr/local/codis3/bin/codis-admin \
        --dashboard={0} \
        --remove-proxy \
        --addr={1} --force".format(dashboard, p_addr)
    print(command)
    subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
    print("{0} {1}".format(dashboard, p_addr), "codis-proxy remove success..")

# 将集群中故障机器所在组的slave升为master
def promote_server(dashboard, gid, s_addr):
    command = "/usr/local/codis3/bin/codis-admin \
        --dashboard={0} \
        --promote-server \
        --gid={1} \
        --addr={2}".format(dashboard, gid, s_addr)
    print(command)
    subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
    print("{0} {1}".format(dashboard, s_addr), " promote-server success..")
def add_proxy(dashboard, s_addr):
    command = "/usr/local/codis3/bin/codis-admin \
        --dashboard={0} \
        --create-proxy  \
        --addr={1}".format(dashboard, s_addr)
    print(command)
    subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
    print("{0} {1}".format(dashboard, s_addr), " add proxy success..")

if __name__ == "__main__":
    dashboard = "192.168.102.252:11080"
    wait = "1"
    dashboard_addr = "192.168.102.252"
    dashboard_port = "11080"
    logger = get_logger("/data/logs/{0}.log".format(dashboard_port))
    topom_url = "http://{0}:{1}/topom".format(dashboard_addr, dashboard_port)
    redisaddr = "192.168.102.252"
    redisport = "7000"
    r = connRedis(redisaddr, redisport, logger)
    init_redis(dashboard_port)

    # 初始化切换锁key，写入集群group、codis-proxy信息
    r.set("codis:cluster:{}:lock:string".format(dashboard_port), 0)  
    try:
        dashboard_json_data = json.loads(requests.get(url=topom_url, timeout=6).text)
        get_cluster_host_ip(dashboard_json_data)
        get_cluster_group_info(dashboard_json_data)
        get_cluster_proxy_info(dashboard_json_data)
    except:
        print("codis dashboard {0}:{1} connect failed...".format(dashboard_addr, dashboard_port))
        print(traceback.format_exc())

    # 监控机器存活状态及切换逻辑
    while True:
        lock = r.get("codis:cluster:{}:lock:string".format(dashboard_port))
        if int(lock) == 0:
            cluster_host_ip = r.smembers("codis:cluster:{0}:host:ip:set".format(dashboard_port))
            for ip in list(cluster_host_ip):
                ip=ip.decode()
                status = check_network(ip)
                print(status)
                proxy_info = r.smembers("codis:cluster:{0}:proxy:set".format(dashboard_port))
                if not status:
                    for addr in list(proxy_info):
                        addr = addr.decode()
                        if str(ip) == str(addr.split(":")[0]):
                            remove_proxy(dashboard, addr)
                            time.sleep(2)
                    group_info = r.hgetall("codis:cluster:{0}:group:hash".format(dashboard_port))
                    for k, v in group_info.items():
                        data = json.loads(v)
                        print(data)
                        if ip == data["master"].split(":")[0]:
                            gid, s_addr = k.decode(), data["slave"]
                            promote_server(dashboard, gid, s_addr)
                            time.sleep(1)
                    r.set("codis:cluster:{0}:lock:string".format(dashboard_port), 1)
                else:
                     proxy_info = [ i.decode() for i in list(proxy_info)]
                     print(proxy_info)
                     s_addr = str(ip)+":18080"
                     if s_addr not in proxy_info:
                         add_proxy(dashboard, s_addr)
                     print("codis3-pika cluster {0} is normal".format(dashboard)) 
        else:
            print("cluster has been switched, please clean redis key")

        time.sleep(15)

