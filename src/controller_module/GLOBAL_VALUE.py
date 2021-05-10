
import networkx as nx
# RYU
from ryu.base import app_manager
from ryu.ofproto import ofproto_v1_5
# for RYU decorator doing catch Event
from ryu.controller.handler import set_ev_cls
from ryu.controller.handler import HANDSHAKE_DISPATCHER, CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller import ofp_event
from ryu.lib.packet import ethernet, arp, icmp, ipv4
from ryu.lib.packet import ether_types, in_proto, icmpv6
from ryu.lib.packet import lldp
from ryu.lib.packet import packet
from ryu.utils import hex_array
from ryu.lib import hub
from ryu import cfg
from nested_dict import *

ARP_SEND_FROM_CONTROLLER = b'\xff\11'  # (bytes)
OpELD_EtherType = 0x1105  
"""Openflow Extend Link Detect"""
OpEQW_EtherType = 0x5157
"""Openflow Extend QoS Weight"""
PATH = nested_dict()
MTU=1500
ip_get_datapathid_port = nested_dict()

G = nx.DiGraph()#: initial value: par1
"""有向拓樸,負責儲存整體網路狀態與拓樸


G的儲存結構

交換機($datapath.id,None)的資訊:
    ::

        GLOBAL_VALUE.G.nodes[($datapath.id,None)]
                                                |["datapath"]=<Datapath object>
                                                |["port"]={$port_id:{
                                                                    "OFPMP_PORT_DESC":{"port_no": 1, "length": 72, "hw_addr": "be:f3:b6:8a:f8:1e", "config": 0,"state": 4, "properties": [{"type": 0, "length": 32, "curr": 2112,"advertised": 0, "supported": 0, "peer": 0, "curr_speed": 10000000,"max_speed": 0}], "update_time": 1552314248.2066813},
                                                                    "OFPMP_PORT_STATS":{'length': 304, 'port_no': 2, 'duration_sec': 17, 'duration_nsec': 235000000, 'rx_packets': 11, 'tx_packets': 10, 'rx_bytes': 698, 'tx_bytes': 684, 'rx_dropped': 0, 'tx_dropped': 0, 'rx_errors': 0, 'tx_errors': 0, 'properties': [{'type': 0, 'length': 40, 'rx_frame_err': 0, 'rx_over_err': 0, 'rx_crc_err': 0, 'collisions': 0}, {'type': 65535, 'length': 184, 'experimenter': 43521, 'exp_type': 1, 'data': [0, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295]}], 'update_time': 1553333684.6574402, 'rx_bytes_delta': 14, 'tx_bytes_delta': 14},
                                                                    #for ARP table
                                                                    "host":{[ip address]:[mac adress]}
                                                                    }
                                                            }
                                                #sec 'active working duration of all port '
                                                |["all_port_duration_s"]=<class 'int'>
                                                #temp when del the port, a new port restart,    #OFPMP_PORT_STATS's duration_sec will be zero
                                                |["all_port_duration_s_temp"]=<class 'int'>
                                                |["FLOW_TABLE"][$table_id<class 'int'>][$priority<class 'int'>][$match<class 'str'>]=<class 'ryu.ofproto.ofproto_v1_5_parser.OFPFlowMod'>
                                                |["now_max_group_id"]=0
                                                |["now_max_xid"]=0
                                                |["GROUP_TABLE"][$group_id<class 'int'>]=<class 'ryu.ofproto.ofproto_v1_5_parser.OFPGroupMod'>
    ::

從交換機`$datapath.id1`的`$datapath.port1` port 到 交換機`$datapath.id2`的`$datapath.port2` port的鏈路資訊:
    ::
    
        GLOBAL_VALUE.G[($datapath.id1,$datapath.port1)][($datapath.id2,$datapath.port2)]|["detect"]|["latency_ms"]:0~max
                                                                                            |["jitter_ms"]:0~max
                                                                                            |["bandwidth_bytes_per_s"]:0~max_bandwidth　重要!!這個代表鏈路可用的頻寬
                                                                                            |["loss_percent"]:0~1%
                                                                                |["tmp"][$seq]={"start":timestamp,"end":timestamp}
    ::
"""

error_search_by_xid=nested_dict(2,dict)
"""
紀錄當初xid所作的openflow message
"""
xid_sem=hub.Semaphore(1)
"""
sadd
""" 


"""dd
利用DiGraph抽象全雙工,並且直接呼叫nx.shortest_path(self.G,(交換機1,None),(交換機2,None),weight="weight")導出路由細節
節點(Node)
    -交換機-這個Node會塞交換機的統計訊息
    -交換機每個port
線(Edge)
    -交換機與port
    -port與port-這個Edge會塞鏈路計算的統計訊息
所以需要check_edge_is_link,check_node_is_switch
"""

"""
            weight=0         Edge          weight=0
            +----+        +-------+        +----+
Switch1  v    | port22 v       | port55 v    |Switch2
+--------+    +--------+       +--------+    +--------+
|(1,None)|    | (1,22) |       | (2,55) |    |(2,None)|
+--------+    +--------+       +--------+    +--------+
    Node   |    ^        |       ^        |    ^  Node
            +----+        +-------+        +----+
            weight=0         Edge          weight=0
"""
# NOTE NODE STRUCT SPEC
"""
node spec
len(ofp_multipart_type)==20
""$"" mean python variable
 
                                    
"""

def get_xid(datapath_id):
    """
    xid是標示每次發送的openflow message的id,當此openflow message發生錯誤
    ddssad
    控制器就會回傳此xid讓控制器知道什麼封包出錯

    dsdsa

    dsadsa
    """
    xid_sem.acquire()
    G.nodes[(datapath_id, None)]["now_max_xid"]=G.nodes[(datapath_id, None)]["now_max_xid"]+1
    _xid=G.nodes[(datapath_id, None)]["now_max_xid"]
    xid_sem.release()
    return _xid

  #!SECTION
# ────────────────────────────────────────────────────────────────────────────────
"""SECTION For DiGraph
+-+-+-+ +-+-+-+-+-+-+-+
|F|o|r| |D|i|G|r|a|p|h|
+-+-+-+ +-+-+-+-+-+-+-+
"""
def check_edge_is_link(ID1, ID2):
    # if port connect to port ,it return True
    if ID1[1] == None or ID2[1] == None:
        return False
    else:
        return True

def check_node_is_switch(ID):
    # if ID=(datapath_id,None) it mean that node is switch
    if ID[1] == None:
        return True
    else:
        return False
def check_node_is_port(ID):
    # if ID=(datapath_id,None) it mean that node is switch
    if ID[1] != None:
        return True
    else:
        return False
#!SECTION