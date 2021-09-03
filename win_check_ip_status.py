from ping3 import ping, verbose_ping
import re
import time

def ping_some_ip(host):
    second = ping(host,timeout=2,unit='s')
    return second

if __name__ == '__main__':
    a=0
    b=0
    start_time=time.time()
    file_path=r"F:\work\log\iplist"
    err_path=r'F:\work\log\err_ip.txt'
    acc_path=r'F:\work\log\acc_ip.txt'
    with open(file_path,mode="r")as f:
        result=f.readlines()
    result = [re.sub("\n","",i) for i in result ]
    for i in result:
        print(time.localtime().tm_min,time.localtime().tm_sec)
        rets=ping_some_ip(i)
        if rets is None:
            b+=1
            print('ping{0}失败！'.format(i))
            with open(err_path,mode="a")as f:
                f.write(i+"\n")
        else:
            a+=1
            print('ping-{}成功，耗时{}ms'.format(i,rets))
            with open(acc_path,mode="a")as f:
                f.write(i+"\n")
    stop_time=time.time()
    print("耗时{0}s".format(stop_time - start_time))
    print("ping成功的一共{0}个".format(a))
    print("ping失败的一共{0}个".format(b))