
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



"""當你要自創權重名稱 需要在這裡註冊以便初始化"""
weight_name_regist=["weight","ppinin"]
route_control_sem=hub.Semaphore(1)

active_route_run=False#是否需要主動模塊

active_rl_in_active_route=True#是否需要啟動強化學習
rl_accept_tos=[192,111]#設定哪些tos需要強化學習優化 如果全部需要強化學習優化會導致啟動緩慢 因為action過大

"""當從強化學習拿到策略才需要開始更新"""
FLOW_ENTRY_IDLE_TIMEOUT=0#sec 0代表沒有TIMEOUT

"""當flow entry多久沒有流量就就可刪除"""
MAX_K_SELECT_PATH=4#k shortest path最多選擇幾條多路徑
"""計算reward需要先告訴公式範圍多少"""
MAX_Loss_Percent=0.2
MAX_Jitter_ms=200#ms 需要預設最大的jitter可能範圍
MAX_DELAY_ms=50#ms需要預設最大的jitter可能範圍

MAX_DELAY_TO_LOSS_ms=1000#ms
 
"""多長的延遲被當作遺失"""
MAX_bandwidth_bytes_per_s=1000000#最大可用頻寬


ARP_SEND_FROM_CONTROLLER = b'\xff\11'  # (bytes)
OpELD_EtherType = 0x1105  
"""Openflow Extend Link Detect"""
OpEQW_EtherType = 0x5157
"""Openflow Extend QoS Weight"""
PATH = nested_dict()
"""ffdd
Tos(8bit)
QoS
bit 11     00       11      11
    delay  jitter   loss    bandwidth
priority是抽象網路切片 依靠Tos(8bit)0~255
Tos*2
__________________________________________________
table:2結構
        .
        .以此類推
        .
priority:4 Tos:1 
priority:3 Tos:1 備用路線

priority:2 Tos:0 dst:10.0.0.1
priority:1 Tos:0 dst:10.0.0.1 備用路線為了在動態路由 切換時的備用路線
priority:0 負責找不道路徑去問控制器
__________________________________________________

利用vlan_id動態切換?

起點交換機    priority:2  Tos:0 
            priority:1  Tos:0  
從頭
-s4-s3
|p1 p1
s1-s2-s3  
p2 p2
p1 p1 p1
::

    GLOBAL_VALUE.PATH[dst][priority]|["cookie"]=<class 'int'>
                            |["path"]=[[(2, 3), (2, None), (2, 2), (3, 3), (3, None), (3, 4)]]
                            |["weight"][1,2]
                            |["graph"]= nx.DiGraph()
                    
::
                    
"""

reward_max_size=3
ALL_REWARD=0
REWARD=nested_dict()
"""
這個負責統計SRC->DST路線品質
是給強化學習反饋學習用的
來源與目的地在同的交換機就不統計

::

    GLOBAL_VALUE.REWARD[SRC][dst][priority]|
                                            |["package"][封包]["start"]=time.time()
                                                             |["end"]=time.time()
                                            |["detect"]|["latency_ms"]:0~max
                                                        |["jitter_ms"]:0~max
                                                        |["bandwidth_bytes_per_s"]:0~max_bandwidth　重要!!這個代表封包傳送的頻寬
                                                        |["loss_percent"]:0~1%
::
                    
"""

MTU=1500
ip_get_datapathid_port = nested_dict()

reuse_cookie={}
cookie=1

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
sem = hub.Semaphore(1)
"""負責mutex get_cookie"""
barrier_lock={}
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


def get_cookie(dst,priority):
    """
    每個dst-ip下的其中一個priority有全域唯一cookie號碼
    這裡的priority代表不同Qos的分化

    .. image:: ../../../../../src/controller_module/aa.drawio.svg
    """
    global cookie
    # Semaphore(1)
    # 表示一次只能有一個人進來拿cookie
    # 類似mutex lock但是eventlet沒有mutex我就用Semaphore代替
    #reuse_cookie={}
    if PATH[dst][priority]["cookie"]!={}:    
        return PATH[dst][priority]["cookie"]
    else:
        sem.acquire()
        if len(reuse_cookie)==0:
            _cookie = cookie  # 保證不會有兩個人拿到相同cookie
            cookie = cookie+1  # FIXME 這個數值有最大值(2^32-1) 需要回收
            #reuse_cookie[_cookie]=True
        else:
            _cookie=list(reuse_cookie.keys())[0] 
            del reuse_cookie[_cookie]
        PATH[dst][priority]["cookie"]=_cookie
        sem.release()
        return _cookie


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
    """
    因為我們抽象交換機與port之間也有edge(目的是讓networkx自動生成包含port的路徑策略)
    所以需要辨別edge是"真實鏈路"與"交換機與port"
    """
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


zmq_socket=None

 


"""這裡不能改單純給兩個線程溝通是否可以開始更新網路"""
NEED_ACTIVE_ROUTE=False#主動模塊需要等待 強化學習跟新權重後才更新路由
 