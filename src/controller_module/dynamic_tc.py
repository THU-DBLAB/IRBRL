"""
這裡程式可以動態改變鏈路網路狀態目的是更靈活的模擬改變網路
delay-distro=jitter
https://github.com/Lu-Yi-Hsun/tcconfig#set-traffic-control-tcset-command
sudo tcset s2-eth1 --delay 30ms --rate 10Kbps --loss 50.1% --delay-distro 10ms  --overwrite
"""

import zmq
from multiprocessing import Process
import os
import time
import random
def tc(interface="s1-eth1",delay=1,bw=1,loss=0.2,jitter=2): 
     
    command="sudo tcset %s --delay %dms --rate %dKbps --loss %f%% --delay-distro %dms  --overwrite"%(interface,delay,bw,loss,jitter)
    print(command)
    print(os.system(command))

def entry(interface_list):
     
    while True:
        for i in interface_list:
            print(i)
            
            jobs = []
            interface=i
            delay=random.randint(1, 1000)
            bw=1000000
            loss=random.randint(0, 100)/100
            jitter=random.randint(1, 100)
            p1 = Process(target=tc,args=(interface,delay,bw,loss,jitter,))
            jobs.append(p1)
            p1.start()

            for j in jobs:
                j.join()
                
        time.sleep(10)