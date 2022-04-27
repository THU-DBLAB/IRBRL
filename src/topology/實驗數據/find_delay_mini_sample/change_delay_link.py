import os 

import time

while True:
    print("change s2-eth14 100ms")
    a=os.system("sudo tc qdisc replace dev s2-eth14 root netem delay 100ms")
    print(a)
    os.system("sudo tc qdisc replace dev s2-eth12 root netem delay 0ms")
    time.sleep(10)
    print("change s2-eth12 100ms")
    os.system("sudo tc qdisc replace dev s2-eth12 root netem delay 100ms")
    os.system("sudo tc qdisc replace dev s2-eth14 root netem delay 0ms")
    time.sleep(10)