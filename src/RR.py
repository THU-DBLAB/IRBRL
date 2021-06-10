
# 2019
# Authour: Lu-Yi-Hsun
# Using visual code
# https://marketplace.visualstudio.com/items?itemName=ExodiusStudios.comment-anchors
import time
import logging
from controller_module import route_module
import networkx as nx
import json
from controller_module.utils import log, dict_tool
from controller_module.tui import tui
from controller_module.route_metrics import formula
from nested_dict import *
import numpy as np
# RYU
from ryu.base import app_manager
from ryu.ofproto import ofproto_v1_5
# for RYU decorator doing catch Event
from ryu.controller.handler import set_ev_cls
from ryu.controller.handler import HANDSHAKE_DISPATCHER, CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller import ofp_event
 
from ryu.lib.packet import ether_types, in_proto, icmpv6
from ryu.lib.packet import lldp
from ryu.lib.packet import packet
from ryu.utils import hex_array
from ryu.lib import hub
from ryu import cfg
from itertools import islice
import copy
import sys
from multiprocessing import Process
import zmq

from controller_module import RL
from controller_module import dynamic_tc
from controller_module import OFPT_FLOW_MOD
from controller_module import GLOBAL_VALUE
from controller_module.monitor_module import MonitorModule
from controller_module.route_module.route_module import RouteModule
from controller_module.route_module import path_select
 

#---------------------------------------------------
"""
                        客製化權重計算演算法
"""
#---------------------------------------------------

def set_weight_alog(self,graph,jitter,loss,bw,delay_one_packet):
    "這裡可以客製化自己的演算法,負責計算鏈路權重,我所提出的強化學習就是在算這個數值"
    graph["kk"]=bw
    
MonitorModule.set_weight_call_back_function=set_weight_alog


def tos_select_alog(self,tos):
    "可以根據不同tos選擇不同權重做出不同選擇"
    if tos==0:
        return "kk"
    else:
        return "kk"
RouteModule.Qos_Select_Weight_Call_Back=tos_select_alog
#---------------------------------------------------
"""
                        客製化鏈路選擇演算法
"""
#---------------------------------------------------


RouteModule.path_selecter=path_select.k_shortest_path_loop_free_version
"設定交換機選擇路徑的演算法"


#---------------------------------------------------

class RinformanceRoute(app_manager.RyuApp):
    """
    控制器執行的主程式 `ryu-managment RR.py`
    """
    OFP_VERSIONS = [ofproto_v1_5.OFP_VERSION]
    _CONTEXTS = {
    'cc': MonitorModule,"ccc":RouteModule
    }
    "設定控制器openflow的版本"
    al_module = Process(target=RL.entry, args=())
    "強化學習模塊"
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    "確認交換機是否收到OFPT_BARRIER_REPLY :py:mod:`~RR.RinformanceRoute` "
    def __init__(self, *args, **kwargs):
        # SECTION __init__
        #ai模組利用zmq溝通
        #
        #self._start_dynamic_tc_module_thread = hub.spawn(self.start_dynamic_tc_module)

        #  Socket to talk to server
        self.al_module.start()
        print("Connecting to hello world server…")
        self.socket.connect("tcp://localhost:5555")
        for request in range(10):
            print("Sending request %s …" % request)
            self.socket.send(b"Hello")
            #  Get the reply.
            message = self.socket.recv()
            print("Received reply %s [ %s ]" % (request, message))
        print("請等拓樸探索完畢")

         
        # run app_manager.RyuApp oject's __init__()
        super(RinformanceRoute, self).__init__(*args, **kwargs)
         
      
     
        self.TUI_Mapping = []
        # init networkx
         

        # NOTE Start Green Thread
        self._handle_route_thread = []
 
   
# ────────────────────────────────────────────────────────────────────────────────
    """SECTION Green Thread
    +-+-+-+-+-+ +-+-+-+-+-+-+
    |G|r|e|e|n| |T|h|r|e|a|d|
    +-+-+-+-+-+ +-+-+-+-+-+-+
    """
# ────────────────────────────────────────────────────────────────────────────────
    
    def start_dynamic_tc_module(self):
        print("start_dynamic_tc_module等待拓樸完成")
        hub.sleep(20)
        interface_list=[]
        for node_id in GLOBAL_VALUE.G.copy().nodes:
            if GLOBAL_VALUE.check_node_is_port(node_id):
                datapath_id=node_id[0]
                port_id=node_id[1]
                interface_list.append("s"+str(datapath_id)+"-eth"+str(port_id))

        self._dynamic_tc_module = Process(target=dynamic_tc.entry, args=(interface_list,))
        self._dynamic_tc_module.start()

         
    # NOTE Update tui

    def _update_tui(self):
        title = """
███████╗██████╗ ███╗   ██╗    ███╗   ███╗ ██████╗ ███╗   ██╗██╗████████╗ ██████╗ ██████╗
██╔════╝██╔══██╗████╗  ██║    ████╗ ████║██╔═══██╗████╗  ██║██║╚══██╔══╝██╔═══██╗██╔══██╗
███████╗██║  ██║██╔██╗ ██║    ██╔████╔██║██║   ██║██╔██╗ ██║██║   ██║   ██║   ██║██████╔╝
╚════██║██║  ██║██║╚██╗██║    ██║╚██╔╝██║██║   ██║██║╚██╗██║██║   ██║   ██║   ██║██╔══██╗
███████║██████╔╝██║ ╚████║    ██║ ╚═╝ ██║╚██████╔╝██║ ╚████║██║   ██║   ╚██████╔╝██║  ██║
╚══════╝╚═════╝ ╚═╝  ╚═══╝    ╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝Author:Lu-Yi-Hsun
        """
        Mapping_idx = 0
        MAX_TUI_LINE = 300
        for idx, i in enumerate(title.split("\n")):
            self.TUI_Mapping.append(i)
            Mapping_idx = idx
        for i in range(MAX_TUI_LINE):
            self.TUI_Mapping.append("")
        Mapping_start = Mapping_idx+1
        while True:
            Mapping_idx = Mapping_start
            for node_id in GLOBAL_VALUE.G.copy().nodes:
                if GLOBAL_VALUE.check_node_is_switch(node_id):
                    switch_title = Mapping_idx
                    Mapping_idx += 1
                    if_EDGE_SWITCH = ""
                    for port in GLOBAL_VALUE.G.copy().nodes[node_id]["port"].keys():
                        host = GLOBAL_VALUE.G.nodes[node_id]["port"][port]["host"]
                        if host != {}:
                            if_EDGE_SWITCH = "Edge Switch"
                        stats = GLOBAL_VALUE.G.nodes[node_id]["port"][port]["OFPMP_PORT_STATS"]
                        desc = GLOBAL_VALUE.G.nodes[node_id]["port"][port]["OFPMP_PORT_DESC"]
                        line = "★ port"+str(port)+" state "+str(desc["state"])+" duration_sec "+str(stats["duration_sec"])+" rx_bytes "+str(stats["rx_bytes"])+" tx_bytes "+str(
                            stats["tx_bytes"])+" rx_bytes_delta "+str(stats["rx_bytes_delta"])+" tx_bytes_delta "+str(stats["tx_bytes_delta"])+" host "+str(host)
                        self.TUI_Mapping[Mapping_idx] = line
                        Mapping_idx += 1

                    line = "datapath ID"+str(node_id)+" "+if_EDGE_SWITCH
                    self.TUI_Mapping[switch_title] = line
                    line = "all_port_duration_s " + \
                        str(GLOBAL_VALUE.G.nodes[node_id]["all_port_duration_s"])
                    self.TUI_Mapping[Mapping_idx] = line
                    """
                    'duration_sec': 26664, 'duration_nsec': 862000000, 'rx_packets': 22, 'tx_packets': 19
                    5, 'rx_bytes': 1636, 'tx_bytes': 12016, 'rx_dropped': 0, 'tx_dropped': 0, 'rx_errors': 0, 'tx_errors': 0
                    """
                    Mapping_idx += 1
                    self.TUI_Mapping[Mapping_idx] = ""
                    Mapping_idx += 1
                    self.TUI_Mapping[Mapping_idx] = "Show Flow Entry"
                    Mapping_idx += 1
                    for table_id in GLOBAL_VALUE.G.copy().nodes[node_id]["FLOW_TABLE"]:
                        for priority in GLOBAL_VALUE.G.copy().nodes[node_id]["FLOW_TABLE"][table_id]:
                            for match in GLOBAL_VALUE.G.copy().nodes[node_id]["FLOW_TABLE"][table_id][priority]:
                                self.TUI_Mapping[Mapping_idx] = "table_id: "+str(
                                    table_id)+" priority: "+str(priority)+" match: "+str(match)
                                Mapping_idx += 1

            self.TUI_Mapping[Mapping_idx] = "Topology Link"
            Mapping_idx += 1
            # self.TUI_Mapping[Mapping_idx]=str(GLOBAL_VALUE.G.edges())
            # print(GLOBAL_VALUE.G.edges())
            for edge in list(GLOBAL_VALUE.G.edges()):
                edge_id1 = edge[0]
                edge_id2 = edge[1]
                if GLOBAL_VALUE.check_edge_is_link(edge_id1, edge_id2):
                    # GLOBAL_VALUE.G[start_switch][end_switch]["port"][end_switch]
                    ed = GLOBAL_VALUE.G[edge_id1][edge_id2]
                    edge_start = "datapath ID " + \
                        str(edge_id1[0]) + " port_no "+str(edge_id1[1])
                    edge_end = "datapath ID " + \
                        str(edge_id2[0]) + " port_no "+str(edge_id2[1])

                    edge_data = edge_start+" ---> "+edge_end

                    self.TUI_Mapping[Mapping_idx] = edge_data
                    Mapping_idx += 1

                    link_data = ""

                    loss_percent = str(ed["detect"]["loss_percent"])
                    bandwidth_bytes_per_s = str(
                        ed["detect"]["bandwidth_bytes_per_s"])
                    latency_ms = str(ed["detect"]["latency_ms"])
                    jitter_ms = str(ed["detect"]["jitter_ms"])

                    link_data = "loss_percent:"+loss_percent + \
                        " "+"bandwidth_bytes_per_s:"+bandwidth_bytes_per_s+" " + \
                            "latency_ms:"+latency_ms+" "+"jitter_ms"+jitter_ms
                    # print(link_data)
                    self.TUI_Mapping[Mapping_idx] = link_data
                    Mapping_idx += 1
  #              GLOBAL_VALUE.G[start_switch][end_switch]["detect"][link_index]["jitter_ms"]=jitter#millisecond
   #             GLOBAL_VALUE.G[start_switch][end_switch]["detect"][link_index]["loss_percent"]=loss#%how many percent of the packet loss
    #            GLOBAL_VALUE.G[start_switch][end_switch]["detect"][link_index]["bandwidth_bytes_per_s"]=bw#
     #           GLOBAL_VALUE.G[start_switch][end_switch]["detect"][link_index]["latency_ms"]=delay_one_packet#from a to b ,just one way ,millisecond
      #          GLOBAL_VALUE.G[start_switch][end_switch]["weight"]=formula.OSPF(bw*8)

            for i in range(30):
                self.TUI_Mapping[Mapping_idx] = ""
                Mapping_idx += 1

            hub.sleep(1)

            # self.TUI_Mapping[1]="duration_sec"+str(GLOBAL_VALUE.G.nodes[1]["port"][1]["OFPMP_PORT_STATS"]["duration_sec"])
    # NOTE Run tui
    def _run_tui(self):
        tui.Screen(self.TUI_Mapping)
    def active_route(self):
        hub.sleep(10)
        print("主動模塊啟動")
        while True:
            self.route_control_sem.acquire()
            for dst, v in list(GLOBAL_VALUE.PATH.items()):
                dst_datapath_id = GLOBAL_VALUE.ip_get_datapathid_port[dst]["datapath_id"]
                dst_port = GLOBAL_VALUE.ip_get_datapathid_port[dst]["port"]
                for priority,v in list(GLOBAL_VALUE.PATH[dst].items()):
                    src_datapath_id_set=set()
                    if len(GLOBAL_VALUE.PATH[dst][priority]["path"])!=0:
                        for path in GLOBAL_VALUE.PATH[dst][priority]["path"]:
                            src_datapath_id_set.add(path[0])
                    else:
                        continue
                    all_route_path_list=[]
                    for src_datapath_id in src_datapath_id_set:
                        # 拿出目的地port number
                        route_path_list_go,_=route_module.k_shortest_path_loop_free_version(self,4,src_datapath_id[0],src_datapath_id[1],dst_datapath_id,dst_port)
                        for idx,i in enumerate(route_path_list_go):
                            all_route_path_list.append(route_path_list_go[idx])
                    weight_list_go = [1 for _ in range(len(all_route_path_list))]
                    tos=priority-1
                    print("------動態資訊-----------")
                    print("動態",dst)
                    print("src_datapath_id_set",src_datapath_id_set)
                    print(all_route_path_list)
                    print("-----------------")
                    self.setting_multi_route_path(all_route_path_list, weight_list_go, dst,tos=tos,idle_timeout=10)
            self.route_control_sem.release()
            #這個設定的時間要大於idle timeout
            hub.sleep(20)
            print("動態gogo")
     

# !SECTION
