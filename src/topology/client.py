import socket
import sys
import time
from secrets import choice
import string
import json
 
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: {} <server IP address> <port>".format(sys.argv[0]))
        sys.exit(1)

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #TOS最後兩個BIT(ECN)無法在應用層設定所以固定保留0
    client.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, 0b11000000)
    client.connect((sys.argv[1], int(sys.argv[2])))
    index=1

    while True:
        rs=''.join([choice(string.ascii_uppercase + string.digits) for _ in range(55)])
        sends={"time":time.time(),"rand":rs}
        client.send(str(json.dumps(sends)).encode())
        print(index)
        index=index+1
        time.sleep(1)
         
        
   