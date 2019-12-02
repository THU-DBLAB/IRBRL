import zmq
import time
import json
import networkx as nx
import matplotlib.pyplot as plt
from collections import defaultdict


def nested_dict2(n, type):
    if n == 1:
        return defaultdict(type)
    else:
        return defaultdict(lambda: nested_dict(n-1, type))

 
from nested_dict import *

nd = nested_dict(2,list)
G = nx.Graph()
G.add_node(2)
G.nodes[2]["SS"]=nested_dict2(2,list)
G.nodes[2]["SS"]["11"]["22"]=[2]
print(nx.node_link_data(G))
context = zmq.Context()

socket = context.socket(zmq.REP)
socket.bind ("tcp://127.0.0.1:7788")

while True:
     
    j=socket.recv_json()
    print(j,type(j))
    socket.send_json(nx.node_link_data(G))
    #time.sleep(0.5)