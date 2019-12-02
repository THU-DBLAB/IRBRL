import zmq
 
context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.connect ("tcp://127.0.0.1:7788")
 
#socket.send_json(a)
trade=socket.recv_json() 
active_id=trade["msg"]["body"]["active_id"]
direction=trade["msg"]["body"]["direction"]
amount=1
print( )