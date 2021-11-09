import os
import socket
import time
import json
PORT = int(os.environ.get("PORT", "12345"))

if __name__ == "__main__":
    server = socket.socket()
    server.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, 4)
    server.bind(("", PORT))
    server.listen(1)
    print("Server listening on port: {}".format(PORT))
    counter = 0
    client, addr = server.accept()
    print("Accepted connection from: {}".format(addr))
    counter += 1
    while True:
        data = client.recv(1024)
        print(data)
        data_d=json.loads(data)
        print((time.time()-float(data_d["time"]))*1000)
         
        