
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
import os
from controller_module import RL
from controller_module import dynamic_tc
from controller_module import OFPT_FLOW_MOD
from controller_module import GLOBAL_VALUE
from controller_module.monitor_module import MonitorModule
from controller_module.route_module.route_module import RouteModule
from controller_module.route_module import path_select
import gym, ray
from ray.rllib.agents import ppo
import json
import socket
import time
import json
import threading
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
     
    "強化學習模塊"
     
    "確認交換機是否收到OFPT_BARRIER_REPLY :py:mod:`~RR.RinformanceRoute` "
    def __init__(self, *args, **kwargs):
        # SECTION __init__
        #ai模組利用zmq溝通
        #
        #self._start_dynamic_tc_module_thread = hub.spawn(self.start_dynamic_tc_module)

        #  Socket to talk to server
        
        
        print("_rl_zmq_connecter_thread")
        self._rl_zmq_connecter_thread=threading.Thread(target=self.rl_zmq_connecter, args=())
        self._rl_zmq_connecter_thread.start()

        print("al_module")

        self.al_module = Process(target=RL.entry, args=())
        self.al_module.start()
        print("al_module ok")
        # run app_manager.RyuApp oject's __init__()
        super(RinformanceRoute, self).__init__(*args, **kwargs)
         
      
     
        self.TUI_Mapping = []
        # init networkx
         

        # NOTE Start Green Thread
        self._handle_route_thread = []
        #self._thread_RL_entry = hub.spawn(self.RL_entry)
         

 
    def RL_entry(self):
        hub.sleep(20)
        count_edge=self.check_all_edge()
        #  Send reply back to client
        _,observation_space=self.one_row_observation()
        init_RL={"observation_call_back":"","action_space":count_edge,"observation_space":observation_space}
        ray.init()
        trainer = ppo.PPOTrainer(env=RL.RL_CORE, config={"gamma":0,"lr": 0.1,
            "env_config": init_RL,  # config to pass to env class
        })
        while True:
            print('啟動AI模組')
             
            trainer.train()
            hub.sleep(5)
            #trainer.save()
            #  Wait for next request from client
         
# ────────────────────────────────────────────────────────────────────────────────
    """SECTION Green Thread
    +-+-+-+-+-+ +-+-+-+-+-+-+
    |G|r|e|e|n| |T|h|r|e|a|d|
    +-+-+-+-+-+ +-+-+-+-+-+-+
    """
# ────────────────────────────────────────────────────────────────────────────────
    def check_all_edge(self)->int:
        #取出所有交換機的port

        #這裡必須等待所有交換機都連線控制器
        #FIXME 等待有更好的寫法
         
        while True:
            port_check=nested_dict(2,str)

            #確認port是否連接為host
            for node_id in GLOBAL_VALUE.G.copy().nodes:
                if GLOBAL_VALUE.check_node_is_switch(node_id):
                    for k in GLOBAL_VALUE.G.nodes[node_id]["port"]:
                        port_check[node_id[0]][k]=None
                        
                        if len(GLOBAL_VALUE.G.nodes[node_id]["port"][k]["host"])!=0:
                            pass        
                            port_check[node_id[0]][k]="host"      
            #確認port是否連接為edge
            count_edge=0
            for edge in list(GLOBAL_VALUE.G.edges()):
                edge_id1 = edge[0]
                edge_id2 = edge[1]
                
                if GLOBAL_VALUE.check_edge_is_link(edge_id1, edge_id2):
                    port_check[edge_id1[0]][edge_id1[1]]="edge"
                    port_check[edge_id2[0]][edge_id2[1]]="edge"
            print(port_check,"check_all_edge")
            #確認是否每個port連接對象完成
            check_ok=True
            count_edge=0
            for datapath_id in port_check:
                for port in port_check[datapath_id]:
                    if port_check[datapath_id][port]==None:
                        check_ok=False
                    elif port_check[datapath_id][port]=="edge":
                        count_edge=count_edge+1
            print(port_check,"check_all_edge2")
             
            if check_ok and count_edge!=0:
                return count_edge
            time.sleep(1)
            
    #各種observation版本
    #什麼結構給強化學習
    def one_row_observation(self):
        
         
        while True:
            jitter_ms=[]
            loss_percent=[]
            bandwidth_bytes_per_s=[]
            latency_ms=[]
            for edge in list(GLOBAL_VALUE.G.edges()):
                edge_id1 = edge[0]
                edge_id2 = edge[1]
                if GLOBAL_VALUE.check_edge_is_link(edge_id1, edge_id2):
                    #放入拓樸
                    
                    jitter_ms.append(GLOBAL_VALUE.G[edge_id1][edge_id2]["detect"]["jitter_ms"])
                    loss_percent.append(GLOBAL_VALUE.G[edge_id1][edge_id2]["detect"]["loss_percent"])
                    bandwidth_bytes_per_s.append(GLOBAL_VALUE.G[edge_id1][edge_id2]["detect"]["bandwidth_bytes_per_s"])
                    latency_ms.append(GLOBAL_VALUE.G[edge_id1][edge_id2]["detect"]["latency_ms"])
            ans=None
            try:
                jitter_ms=np.interp(jitter_ms,(0,GLOBAL_VALUE.MAX_Jitter_ms),(0,1))
                loss_percent=np.interp(loss_percent,(0,GLOBAL_VALUE.MAX_Loss_Percent),(0,1))
                bandwidth_bytes_per_s=np.interp(bandwidth_bytes_per_s,(0,GLOBAL_VALUE.MAX_bandwidth_bytes_per_s),(0,1))
                latency_ms=np.interp(latency_ms,(0,GLOBAL_VALUE.MAX_DELAY_TO_LOSS_ms),(0,1))
                ans=np.concatenate((jitter_ms,loss_percent,bandwidth_bytes_per_s,latency_ms))
                 
            except:
                print("one_row_observation error")
             
            if len(ans.tolist())!=0:
                return ans.tolist(),len(ans.tolist())
            time.sleep(0.5)
            

    def clear_temp_file(self):
        try:
            os.remove("controller_module/.for_robot")  
            os.remove("controller_module/.for_rl")
        except:
            pass
        
    def rl_zmq_connecter(self):
        """
        這裡負責傳送必要資訊給強化學習並且拿回策略
        """
        self.clear_temp_file()
        print("請至少等待所有交換機都連線完成")
        time.sleep(10)

        #FIXME 這裡要處理等待拓樸探索完成,必須等待拓樸建構完成才知道強化學習輸出的結構,缺點無法應用在拓樸頻繁更動的環境
        count_edge=self.check_all_edge()
         
        
        #  Send reply back to client
        _,observation_space=self.one_row_observation()
        init_RL={"action_space":count_edge,"observation_space":observation_space}
        print(init_RL)
        init_RL_str=json.dumps(init_RL)
        action_uuid=0
        self.write_for_rl(str(init_RL_str))
        
        while True:
            #  Wait for next request from client
             
            message = self.read_for_robot()
            
            #  Do some 'work'
             
            try:
                message_list=json.loads(message)
                if int(message_list["action_uuid"])<=action_uuid:
                    #為了確保action是新的
                    continue
                action_uuid=int(message_list["action_uuid"])
                message_list=message_list["action"]
            except:
                hub.sleep(1)
                continue
            print("ACTIONs",message_list)
            e_index=0
            #把ai回傳的權重放入拓樸
            for edge in list(GLOBAL_VALUE.G.edges()):
                edge_id1 = edge[0]
                edge_id2 = edge[1]
                if GLOBAL_VALUE.check_edge_is_link(edge_id1, edge_id2):
                    #放入拓樸
                    GLOBAL_VALUE.G[edge_id1][edge_id2]["weight"]=message_list[e_index]
                    e_index=e_index+1
            GLOBAL_VALUE.NEED_ACTIVE_ROUTE=True

            #這裡設定-10為了當沒有封包流動reward應該0但是一直頻繁設定網路我給負號獎勵
            GLOBAL_VALUE.ALL_REWARD=-10
            time.sleep(10)
             
            #  Send reply back to client
            obs,_=self.one_row_observation()
            step_data={"action_uuid":action_uuid,"obs":list(obs),"reward":GLOBAL_VALUE.ALL_REWARD}
            
            #FIXME 回傳
            print("step_data",step_data)
            self.write_for_rl(str(json.dumps(step_data)))
            #socket.send(str(json.dumps(step_data)).encode("utf8"))
    def read_for_robot(self):
        pass 
        while True:  
            try:
                f = open("controller_module/.for_robot", "r")
                a=f.read()
                
                f.close()
                break
            except:
                pass
            time.sleep(0.5)
        return a
    def write_for_rl(self,w):
        f = open("controller_module/.for_rl", "w")
        f.write(w)
        f.close()
        pass

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
   
     

# !SECTION
