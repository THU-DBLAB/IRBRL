
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
from ryu.lib.packet import ethernet, arp, icmp, ipv4
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
from controller_module import RL
from controller_module import dynamic_tc
from controller_module import OFPT_FLOW_MOD
from controller_module import GLOBAL_VALUE
import zmq
 
CONF = cfg.CONF
from controller_module.monitor_module import MonitorModule

from controller_module.route_module import RouteModule
 

 

class RinformanceRoute(app_manager.RyuApp):
    """
    控制器執行的主程式 `ryu-managment RR.py`
    """
    OFP_VERSIONS = [ofproto_v1_5.OFP_VERSION]
    _CONTEXTS = {
    'cc': MonitorModule
    }
    "設定控制器openflow的版本"
    al_module = Process(target=RL.entry, args=())
    "強化學習模塊"
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    
    xid_sem=hub.Semaphore(1)
    route_control_sem=hub.Semaphore(1)#一次只能有一個程式掌控網路
     
    sem = hub.Semaphore(1)#確保每次拿 get_cookie 只能有一個人進入critical section~
    barrier_lock={}#
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
        self.MTU = 1500
        # NOTE Openflow Extend setting
        self.OpEPS = 0  # Openflow Extend Port State
        GLOBAL_VALUE.OpELD_EtherType = 0x1105  # Openflow Extend Link Detect(int)
        GLOBAL_VALUE.OpEQW_EtherType = 0x5157  # Openflow Extend QoS Weight
        #network slicing
        
        self.check_route_is_process_SEM = hub.Semaphore(1)
        self.setting_multi_route_path_SEM= hub.Semaphore(1)

        self.check_route_is_process=nested_dict(3,dict)
        
        "這個是vlan header的ether type"

        """
        # 從1開始,0代表沒有設定cookie
        # 規劃出的src_ip->dst_ip(不管single or multipath)路線與priotity有唯一cookie
        # 該cookie數值會用在flow entry的cookie與group_id共用此數字 所以最大值為2^32-1=4294967295
        # FIXME 需要完成 self.cookie回收機制
        """
        self.cookie = 1 
        self.reuse_cookie={}
        self.dst_priority_cookie=nested_dict()
        # 處理統計路線
        # handle_arp
         
        # https://www.iana.org/assignments/arp-parameters/arp-parameters.xhtml
        # REQUEST = 1
        # REPLY   = 2
        self.ARP_request = 1
        self.ARP_reply = 2
        GLOBAL_VALUE.PATH = nested_dict()  
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

            GLOBAL_VALUE.PATH[dst][priority]|["cookie"]=<class 'int'>
                                    |["path"]=[[(2, 3), (2, None), (2, 2), (3, 3), (3, None), (3, 4)]]
                                    |["weight"][1,2]
                                    |["graph"]= nx.DiGraph()
                                    |["package"]["start"][封包]=time.time()
                                    |["package"]["end"][封包]=time.time()
                                    |["detect"]|["latency_ms"]:0~max
                                                |["jitter_ms"]:0~max
                                                |["bandwidth_bytes_per_s"]:0~max_bandwidth　重要!!這個代表封包傳送的頻寬
                                                |["loss_percent"]:0~1%
                           
        """
        # self.echo_latency[ev.msg.datapath.id] Detect controller --one way---> switch latency
         
        # self.OpELD_start_time[datapath.id][out_port]
         
         
         
        self.mac_get_datapathid_port = nested_dict()
        # GLOBAL_VALUE.G.nodes[datapath.id]["port"][in_port]["host"] can get the same data but GLOBAL_VALUE.G.nodes
        # NOTE can recognize if OpenVswitch is Edge Switch or not
        # The space of the TUI,for draw data
        self.TUI_Mapping = []
        # init networkx
         

        # NOTE Start Green Thread
        self._handle_route_thread = []

        self._active_route_thread = hub.spawn(self.active_route)
        self._active_route_thread2 = hub.spawn(self.active_route2)
        # NOTE Monitor
        
         
        # NOTE Text-based user interface(tui)
        # if CONF.RR.TUI:
        #self._run_tui_htread = hub.spawn(self._run_tui)
        #self._update_tui_htread = hub.spawn(self._update_tui)

        # NOTE GLOBAL_VALUE.G = nx.DiGraph() Design

         
        # NOTE EDGES STRUCT SPEC
        # Support Link Aggregation
        # $list_of_port_id1[0]<->$list_of_port_id2[0]
        # $list_of_port_id1[1]<->$list_of_port_id2[1]
        """
        GLOBAL_VALUE.G[($datapath.id1,$datapath.port1)][($datapath.id2,$datapath.port2)]|["detect"]|["latency_ms"]:0~max
                                                                                           |["jitter_ms"]:0~max
                                                                                           |["bandwidth_bytes_per_s"]:0~max_bandwidth　重要!!這個代表鏈路可用的頻寬
                                                                                           |["loss_percent"]:0~1%
                                                                                |["tmp"][$seq]={"start":timestamp,"end":timestamp}



        """

   
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
   
 
   
     
    
   
  

     

     
 
# ────────────────────────────────────────────────────────────────────────────────
    """SECTION Packet-Out Message
     +-+-+-+-+-+-+-+-+-+-+ +-+-+-+-+-+-+-+
     |P|a|c|k|e|t|-|O|u|t| |M|e|s|s|a|g|e|
     +-+-+-+-+-+-+-+-+-+-+ +-+-+-+-+-+-+-+
    """
# ────────────────────────────────────────────────────────────────────────────────
 
     


# ────────────────────────────────────────────────────────────────────────────────
    # NOTE send_arp_packet

     
    # NOTE send_icmp_packet

    def send_icmp_packet(self, datapath, src="255.255.255", dst="255.255.255"):
        ofp = datapath.ofproto
        parser = datapath.ofproto_parser
        pkt = packet.Packet()
        pkt.add_protocol(ethernet.ethernet(
            ethertype=ether_types.ETH_TYPE_IP))
        pkt.add_protocol(ipv4.ipv4(src=datapath.id, dst=dst, proto=1))
        pkt.add_protocol(
            icmp.icmp(type_=icmp.ICMP_ECHO_REQUEST, code=0, csum=0))
        pkt.serialize()
        data = pkt.data
        match = datapath.ofproto_parser.OFPMatch(
            in_port=ofp.OFPP_CONTROLLER)
        actions = [parser.OFPActionOutput(ofp.OFPP_ALL)]
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=ofp.OFP_NO_BUFFER,
                                  match=match, actions=actions, data=data)
        datapath.send_msg(out)
    # NOTE send_lldp_packet

    def send_lldp_packet(self, datapath, port_no, data_size):
        # data_size 0~1440
        ofp = datapath.ofproto
        parser = datapath.ofproto_parser
        pkt = packet.Packet()
        pkt.add_protocol(ethernet.ethernet(
            ethertype=ether_types.ETH_TYPE_LLDP))
        tlv_chassis_id = lldp.ChassisID(
            subtype=lldp.ChassisID.SUB_LOCALLY_ASSIGNED, chassis_id=str(datapath.id))
        tlv_port_id = lldp.PortID(
            subtype=lldp.PortID.SUB_LOCALLY_ASSIGNED, port_id=str(port_no))
        tlv_ttl = lldp.TTL(ttl=10)
        tlv_end = lldp.End()
        tlvs = (tlv_chassis_id, tlv_port_id, tlv_ttl, tlv_end)
        pkt.add_protocol(lldp.lldp(tlvs))
        pkt.serialize()
        data = pkt.data  # 60bytes
        # bytes in one packet ,can set 0~1440 because MTU Max is 1500
        data = data+bytearray(1440)
        actions = [parser.OFPActionOutput(port=port_no)]
        match = datapath.ofproto_parser.OFPMatch(
            in_port=datapath.ofproto.OFPP_CONTROLLER)
        out = parser.OFPPacketOut(
            datapath=datapath, buffer_id=ofp.OFP_NO_BUFFER, match=match, actions=actions, data=data)

    # !SECTION

# ────────────────────────────────────────────────────────────────────────────────
    """ SECTION Asynchronous Messages
     +-+-+-+-+-+-+-+-+-+-+-+-+ +-+-+-+-+-+-+-+-+
     |A|s|y|n|c|h|r|o|n|o|u|s| |M|e|s|s|a|g|e|s|
     +-+-+-+-+-+-+-+-+-+-+-+-+ +-+-+-+-+-+-+-+-+
    """
# ────────────────────────────────────────────────────────────────────────────────
    
    # SECTION OFPT_FLOW_REMOVED
    @set_ev_cls(ofp_event.EventOFPFlowRemoved, MAIN_DISPATCHER)
    def _flow_removed_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser
        # print(type(msg.match))
        # print(GLOBAL_VALUE.G.nodes[(int(dp.id),None)]["FLOW_TABLE"])
        try:
            del GLOBAL_VALUE.G.nodes[(datapath.id, None)]["FLOW_TABLE"][int(msg.table_id)][int(msg.priority)][str(msg.match)]
        except:
            pass
        #msg.cookie
        #print(msg.cookie,"刪除")
         
        ipv4_dst=msg.match.get("ipv4_dst")
        self.sem.acquire()
        if ipv4_dst!=None:
            #GLOBAL_VALUE.PATH[ipv4_dst][msg.priority]["path"]
            #print(type(msg.match),msg.match.get("ipv4_dst"))
            #當flow entry刪除 相應的group entry也要一起刪除
            """
            mod = ofp_parser.OFPGroupMod(datapath, command=ofp.OFPGC_DELETE,group_id=msg.cookie)
            datapath.send_msg(mod)
            try:
                del GLOBAL_VALUE.G.nodes[(datapath.id,None)]["GROUP_TABLE"][msg.cookie]
            except:
                pass
            """
            #self.reuse_cookie[msg.cookie]=True#回收cookie
            #當路徑上其中一個交換機flow entry刪除 就當作此路徑已經遺失 需要重新建立
            for path in GLOBAL_VALUE.PATH[ipv4_dst][msg.priority]["path"].copy():
                for i in path[2::3]:
                    set_datapath_id = i[0]
                    if datapath.id==set_datapath_id:
                        #print("刪除",path)
                        if path in GLOBAL_VALUE.PATH[ipv4_dst][msg.priority]["path"]:
                            GLOBAL_VALUE.PATH[ipv4_dst][msg.priority]["path"].remove(path)
        self.sem.release()            
            
             

        
        if msg.reason == ofp.OFPRR_IDLE_TIMEOUT:
            reason = 'IDLE TIMEOUT'
        elif msg.reason == ofp.OFPRR_HARD_TIMEOUT:
            reason = 'HARD TIMEOUT'
        elif msg.reason == ofp.OFPRR_DELETE:
            reason = 'DELETE'
        elif msg.reason == ofp.OFPRR_GROUP_DELETE:
            #print('GROUP DELETE!!!!!!!!!!!!!!!!!!!!!!')
            reason = 'GROUP DELETE'
             
            try:
                del GLOBAL_VALUE.G.nodes[(datapath.id,None)]["GROUP_TABLE"][msg.cookie]
            except:
                pass
        else:
            reason = 'unknown'
        """print('OFPFlowRemoved received: '
                      'table_id=%d reason=%s priority=%d '
                      'idle_timeout=%d hard_timeout=%d cookie=%d '
                      'match=%s stats=%s',
                      msg.table_id, reason, msg.priority,
                      msg.idle_timeout, msg.hard_timeout, msg.cookie,
                      msg.match, msg.stats)"""
    # !SECTION
    # SECTION OFPT_PORT_STATUS
    @set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
    def _port_status_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofp = datapath.ofproto
        ofp_port_state = msg.desc.state
        data = dict_tool.class2dict(msg.desc)
        data["update_time"] = time.time()
        # print(data)
        GLOBAL_VALUE.G.nodes[(datapath.id, None)
                     ]["port"][msg.desc.port_no]["OFPMP_PORT_DESC"] = data
        if msg.reason == ofp.OFPPR_ADD:
            """ADD"""
            pass

        elif msg.reason == ofp.OFPPR_DELETE:
            """DELETE"""

            # doing storage all_port_duration_s_temp
            try:
                GLOBAL_VALUE.G.nodes[(datapath.id, None)]["all_port_duration_s_temp"] = int(GLOBAL_VALUE.G.nodes[(datapath.id, None)]["all_port_duration_s_temp"])+int(
                    GLOBAL_VALUE.G.nodes[(datapath.id, None)]["port"][msg.desc.port_no]["OFPMP_PORT_STATS"]["duration_sec"])
            except:
                GLOBAL_VALUE.G.nodes[(datapath.id, None)
                             ]["all_port_duration_s_temp"] = 0

            # NOTE Openflow Extend Port State
            # difference with OF1.5 ofp_port_state
            # Implementation add this to port state "0",define the port have been ""DELETE"" by OVSDB
            # data["state"]
            # Openflow Extend Port State= 0 ,sort name:OPEPS /*the port have been ""DELETE"" */
            # OFPPS_LINK_DOWN = 1, /* No physical link present. */
            # OFPPS_BLOCKED = 2, /* Port is blocked */
            # OFPPS_LIVE = 4, /* Live for Fast Failover Group. */
            #data["state"] = self.OpEPS
            GLOBAL_VALUE.G.nodes[(datapath.id, None)
                         ]["port"][msg.desc.port_no]["OFPMP_PORT_DESC"] = data
        elif msg.reason == ofp.OFPPR_MODIFY:
            """MODIFY"""
            if ofp_port_state == ofp.OFPPS_LINK_DOWN:
                """OFPPS_LINK_DOWN"""
                pass
            elif ofp_port_state == ofp.OFPPS_BLOCKED:
                """OFPPS_BLOCKED"""
                pass
                # del GLOBAL_VALUE.G.nodes[datapath.id]["port"][msg.desc.port_no]
            elif ofp_port_state == ofp.OFPPS_LIVE:
                """OFPPS_LIVE"""
                pass
                # GLOBAL_VALUE.G.nodes[datapath.id]["port"].update(msg.desc.port_no)
            else:

                pass
        else:
            reason = 'unknown'
    # !SECTION

# ────────────────────────────────────────────────────────────────────────────────
    """SECTION OFPT_PACKET_IN 
     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+
     |O|F|P|T|_|P|A|C|K|E|T|_|I|N|
     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    """
# ────────────────────────────────────────────────────────────────────────────────

    # NOTE: _packet_in_handler
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        """
        非同步接收來自交換機OFPT_PACKET_IN message

        """
        msg = ev.msg
        datapath = msg.datapath
         
        port = msg.match['in_port']
         
        pkt = packet.Packet(data=msg.data)
        pkt_ethernet = pkt.get_protocol(ethernet.ethernet)
         

        pkt_icmp = pkt.get_protocol(icmp.icmp)
        if pkt_icmp:
            #print("icmp!!!")
            pass
         

        pkt_lldp = pkt.get_protocol(lldp.lldp)
        if pkt_lldp:
            self.handle_lldp(datapath, port, pkt_ethernet, pkt_lldp)
        pkt_ipv4 = pkt.get_protocol(ipv4.ipv4)
        if pkt_ipv4:
             

            # table 1 負責統計
            if msg.table_id == 1:
                self._handle_package_analysis(ev)
            # table 2負責路由
            elif msg.table_id == 2:
                
                # 想要路由但不知道路,我們需要幫它,這屬於被動路由
                self._handle_route_thread.append(hub.spawn(
                    self.handle_route, datapath=datapath, port=port, msg=msg))
               
    # 處理統計路徑 延遲等等 評估此設定好不好

    def _handle_package_analysis(self, ev):
         
        msg = ev.msg
        datapath = msg.datapath
        pkt = packet.Packet(data=msg.data)
        pkt_ipv4 = pkt.get_protocol(ipv4.ipv4)
        src_datapath_id = GLOBAL_VALUE.ip_get_datapathid_port[pkt_ipv4.src]["datapath_id"]
        path_loc = "start" if datapath.id == src_datapath_id else "end"
        # FIXME 這msg.data可以改murmurhas去改變
         
        dscp=int(pkt_ipv4.tos)>>2
        GLOBAL_VALUE.PATH[pkt_ipv4.dst][dscp]["package"][path_loc][msg.data] = time.time()
        for src, v in list(GLOBAL_VALUE.PATH.items()):
            for dst, dst_priority_path in list(v.items()):
                pass
                #print(dst_priority_path["detect"])

    # 被動模塊
    def handle_route_v2(self, datapath, port, pkt_ipv4, data):
        #print(datapath, port, pkt_ipv4,GLOBAL_VALUE.ip_get_datapathid_port[pkt_ipv4.dst])
        if GLOBAL_VALUE.ip_get_datapathid_port[pkt_ipv4.dst] != {}:  # 確保知道目的地在哪裡
            dst_datapath_id = GLOBAL_VALUE.ip_get_datapathid_port[pkt_ipv4.dst]["datapath_id"]
            dst_port = GLOBAL_VALUE.ip_get_datapathid_port[pkt_ipv4.dst]["port"]
            # 選出單一路徑
            # 去
            alog = "weight"  # EIGRP
            route_path_go = nx.shortest_path(
                GLOBAL_VALUE.G, (datapath.id, port), (dst_datapath_id, dst_port), weight=alog)
            self.setting_route_path(route_path_go, pkt_ipv4.dst)
            # 回
            route_path_back = nx.shortest_path(
                GLOBAL_VALUE.G, (dst_datapath_id, dst_port), (datapath.id, port), weight=alog)
            self.setting_route_path(route_path_back, pkt_ipv4.src)
            # 上面只是規劃好路徑 這裡要幫 上來控制器詢問的`迷途小封包` 指引,防止等待rto等等...
            # 你可以測試下面刪除會導致每次pingall都要等待
            ofp = datapath.ofproto
            parser = datapath.ofproto_parser
            match = datapath.ofproto_parser.OFPMatch(in_port=port)
            out_port = route_path_go[2][1]
            actions = [parser.OFPActionOutput(port=out_port)]
            out = parser.OFPPacketOut(datapath=datapath, buffer_id=ofp.OFP_NO_BUFFER,
                                      match=match, actions=actions, data=data)
            datapath.send_msg(out)
            #                       route_path[2::3]
            #[(1, 1), (1, None), (1, 2), (2, 2), (2, None), (2, 1)]
            #                     ^^^^                       ^^^^

            # 多路徑k sort path
            #islice(nx.shortest_simple_paths(GLOBAL_VALUE.G, (1,None), (2,None), weight="weight"), 2)

     
     

     

        # Openflow Extend Link Detect(OpELD) Topology/Link Detect

    # SECTION handle_opeld
     

        # TODO !!!!!!!!!!!!!!!!!!!!!!!!!
    

    # NOTE route
    def route(self):
        pass
    # !SECTION
# ────────────────────────────────────────────────────────────────────────────────
    """SECTION Symmetric Messages
     +-+-+-+-+-+-+-+-+-+ +-+-+-+-+-+-+-+-+
     |S|y|m|m|e|t|r|i|c| |M|e|s|s|a|g|e|s|
     +-+-+-+-+-+-+-+-+-+ +-+-+-+-+-+-+-+-+
    """
# ────────────────────────────────────────────────────────────────────────────────
 

     

        # print('EventOFPEchoReply received: data=%s',(latency*1000))

    # !SECTION
    # NOTE EventOFPErrorMsg

    @set_ev_cls(ofp_event.EventOFPErrorMsg, [HANDSHAKE_DISPATCHER, CONFIG_DISPATCHER, MAIN_DISPATCHER])
    def error_msg_handler(self, ev):
        
        msg = ev.msg
        datapath = msg.datapath
        ofproto = msg.datapath.ofproto
        if msg.type == ofproto.OFPET_FLOW_MOD_FAILED:
            # 這裡就是要設定flow entry但是失敗了 所以需要刪除
            # 因為dict做迴圈都需要複製,防止執行時突然被新插入導致迴圈會錯亂拉QQ
            _G = GLOBAL_VALUE.G.copy()
            _FLOW_TABLE = _G.nodes[(datapath.id, None)]["FLOW_TABLE"]
            for table_id in _FLOW_TABLE:
                for priority in _FLOW_TABLE[table_id]:
                    for match in _FLOW_TABLE[table_id][priority]:
                        mod = _FLOW_TABLE[table_id][priority][match]
                        # 抓到了你這個flow entry設定錯誤 要刪除紀錄喔
                        if mod.xid == msg.xid:
                            del GLOBAL_VALUE.G.nodes[(
                                datapath.id, None)]["FLOW_TABLE"][table_id][priority][match]

        elif msg.type == ofproto.OFPET_GROUP_MOD_FAILED:
            pass
         
        #print("OFPErrorMsg received:", msg.type, msg.code, msg.xid)
        print("___________OFPErrorMsg received_______________")
        print(ofproto.ofp_error_code_to_str(msg.type, msg.code))
        print(datapath.id)
        print(GLOBAL_VALUE.error_search_by_xid[datapath.id][msg.xid])
        print("__________________________")
        print("\n")
        
        self.stop()
        #print(msg.data.decode("utf-8"))

    # FIXME : ryu-manager using ,this function is implement by echo,if switch not reply echo,switch will close

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            pass

        elif ev.state == DEAD_DISPATCHER:
            pass

    # !SECTION

    # !SECTION

# SECTION Route Module
     
    def send_delete_group_mod(self, datapath, group_id: int):
        """
        group_id是給flow entry指引要導到哪個group entry
        """
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser
        #刪除group by group_id
        req = ofp_parser.OFPGroupMod(
            datapath, command=ofp.OFPGC_DELETE, group_id=group_id)
        datapath.send_msg(req)

    def delete_route_path(self, route_path, cookie):
        for i in route_path[-1::-3]:
            # 刪除flow entry根據cookie
            set_datapath_id = i[0]
            tmp_datapath = GLOBAL_VALUE.G.nodes[(set_datapath_id, None)]["datapath"]
            ofp = tmp_datapath.ofproto
            parser = tmp_datapath.ofproto_parser
            match = parser.OFPMatch()
            # 刪除交換機內所有數值為cookie的flow entry
            mod = parser.OFPFlowMod(datapath=tmp_datapath,
                                    priority=1, table_id=ofp.OFPTT_ALL,
                                    command=ofp.OFPFC_DELETE, out_port=ofp.OFPP_ANY, out_group=ofp.OFPG_ANY,
                                    match=match, cookie=cookie, cookie_mask=0xffffffffffffffff
                                    )
            tmp_datapath.send_msg(mod)
            # 接下來刪除group id-不一定會有group但是我一起刪看看
            self.send_delete_group_mod(tmp_datapath, cookie)
            # route_path

    def setting_single_route_path(self, route_path, dst, src=None):
        # 這裡是專門設定singal path 沒有group table介入
        # OFPMatch沒有設定src的好處可以節省flow entry,壞處是有可能發生環形路由不容易控制,該怎麼減少flow entry?需要相關論文
        #route_path=[(2, 3), (2, None), (2, 2), (3, 3), (3, None), (3, 4)]
        # 抽象route_path解說
        # src在交換機2的3號port(2, 3)->2交換機(2, None)->2交換機的2號port(2, 2)->3號交換機的3號port(3, 3)->3號交換機(3, None)->3號交換機的4號port(3, 4)到達dst
        # 設定路徑從後面開始 從(3, 4)到(2, 2) 因為如果一開始就設定前面路線的flow entry封包會開始流動結果後面跟不上設定就開始遺失
        _cookie = GLOBAL_VALUE.get_cookie()
        for i in route_path[-1::-3]:
            set_datapath_id = i[0]
            set_out_port = i[1]
            tmp_datapath = GLOBAL_VALUE.G.nodes[(set_datapath_id, None)]["datapath"]
            ofp = tmp_datapath.ofproto
            parser = tmp_datapath.ofproto_parser
            match = parser.OFPMatch(
                eth_type=ether_types.ETH_TYPE_IP, ipv4_dst=dst, ipv4_src=src)
            action = [parser.OFPActionOutput(port=set_out_port)]
            instruction = [parser.OFPInstructionActions(
                ofp.OFPIT_APPLY_ACTIONS, action)]
            mod = parser.OFPFlowMod(datapath=tmp_datapath,
                                    priority=1, table_id=2,
                                    command=ofp.OFPFC_ADD,
                                    match=match, cookie=_cookie,
                                    instructions=instruction, idle_timeout=60
                                    )
            hub.spawn(OFPT_FLOW_MOD.send_ADD_FlowMod, mod)

        GLOBAL_VALUE.PATH[dst][priority]["cookie"][_cookie] = [route_path]
    #這裡要確保交換機先前設定的動作已經完成
    def send_barrier_request(self, datapath,xid=None):
        
        ofp_parser = datapath.ofproto_parser
        req = ofp_parser.OFPBarrierRequest(datapath)
        req.xid=xid
        datapath.send_msg(req)
    #當交換機已經完成先前的設定才會回傳這個
    @set_ev_cls(ofp_event.EventOFPBarrierReply, MAIN_DISPATCHER)
    def barrier_reply_handler(self, ev):
        #print(ev.msg.)
        msg = ev.msg
        datapath = msg.datapath
        self.barrier_lock[datapath.id]=False
    def wait_finish_switch_BARRIER_finish(self,datapath):
        self.barrier_lock[datapath.id]=True
        self.send_barrier_request(datapath)
        while self.barrier_lock[datapath.id]:
            hub.sleep(0)


    def clear_multi_route_path(self,dst, priority):
        #刪除光光
        set_switch_for_barrier=set()
        if GLOBAL_VALUE.PATH[dst][priority]["path"]!={}:
            cookie=GLOBAL_VALUE.PATH[dst][priority]["cookie"]
            #保證cookie 0不會倍刪除
            if cookie==0:
                return
            for path in GLOBAL_VALUE.PATH[dst][priority]["path"]:
                for i in path[2::3]:
                    set_datapath_id = i[0]
                    tmp_datapath = GLOBAL_VALUE.G.nodes[(set_datapath_id, None)]["datapath"]
                    ofp = tmp_datapath.ofproto
                    parser = tmp_datapath.ofproto_parser
                    """
                    mod = parser.OFPGroupMod(tmp_datapath, command=ofp.OFPGC_DELETE,group_id=cookie)
                     
                    tmp_datapath.send_msg(mod)
                    """
                    match = parser.OFPMatch()
                    mod = parser.OFPFlowMod(datapath=tmp_datapath, table_id=ofp.OFPTT_ALL,
                                            command=ofp.OFPFC_DELETE, out_port=ofp.OFPP_ANY, out_group=ofp.OFPG_ANY,
                                            match=match, cookie=cookie, cookie_mask=0xffffffffffffffff
                                            )
                    tmp_datapath.send_msg(mod)
                    set_switch_for_barrier.add(tmp_datapath)
        for tmp_datapath in set_switch_for_barrier:
            self.wait_finish_switch_BARRIER_finish(tmp_datapath)
        #del GLOBAL_VALUE.PATH[dst][priority]["path"]

    def setting_multi_route_path(self, route_path_list, weight_list, dst, prev_path=[],prev_weight=[],tos=0,idle_timeout=0,hard_timeout=0, delivery_schemes="unicast"):
        self.setting_multi_route_path_SEM.acquire()
        #route_path_list 必須保證free loop
        dscp=tos>>2
        priority=(2*dscp)+1
        _cookie = GLOBAL_VALUE.get_cookie(dst,priority)
         
        for path, weight in zip(route_path_list, weight_list):
            a=""
            for i in path[2::3]:
                a=a+"->"+str(i)
            #print(a)


        # https://osrg.github.io/ryu-book/zh_tw/html/spanning_tree.html
        # delivery_schemes https://en.wikipedia.org/wiki/Routing#Delivery_schemes
        # 單播多路徑unicast
        # FIXME 未來開發多播multicast dst     可能要很多個?
        # 多條路徑(route_path_list)結合每個路徑的權重(weight_list)
        # weight_list[0]代表route_path_list[0]的權重 以此類推
        # 探討group如何select bucket
        # flow_mask_hash_fields    https://github.com/openvswitch/ovs/blob/v2.15.0/lib/flow.c#L2462
        # pick_default_select_group https://github.com/openvswitch/ovs/blob/v2.15.0/ofproto/ofproto-dpif-xlate.c#L4564
        # group_best_live_bucket https://github.com/openvswitch/ovs/blob/v2.15.0/ofproto/ofproto-dpif-xlate.c#L1956
        
        #載入原先的路徑
        for path,weight in zip(prev_path,prev_weight):
            route_path_list.append(path)
            weight_list.append(weight)

        
        
        #紀錄每個交換機需要OUTPUT的
        _switch = nested_dict(2,dict)
        for path, weight in zip(route_path_list, weight_list):
             
            for i in path[2::3]:
         
                set_datapath_id = i[0]
                set_out_port = i[1]
                if _switch[set_datapath_id][set_out_port]!={}:
                    #FIXME 多條路線經過同的路徑 權重利用平均 最小數值為1
                    _switch[set_datapath_id][set_out_port] = max(int((_switch[set_datapath_id][set_out_port]+weight)/2),1)
                else:
                    _switch[set_datapath_id][set_out_port] = weight
        
        #刪除光原先的group entry flow entry重新設定
    
        self.clear_multi_route_path(dst, priority)

         
        #設定只有岔路需要設定group entry
        set_switch_for_barrier=set()
        for set_datapath_id in _switch:
            tmp_datapath = GLOBAL_VALUE.G.nodes[(set_datapath_id, None)]["datapath"]
            ofp = tmp_datapath.ofproto
            parser = tmp_datapath.ofproto_parser
            if len(_switch[set_datapath_id].keys()) >= 2 and set_datapath_id not in set_switch_for_barrier:
                port_list = list(_switch[set_datapath_id].keys())
                group_weight_list = []
                for p in list(_switch[set_datapath_id].keys()):
                    group_weight_list.append(_switch[set_datapath_id][p])
                route_module.send_add_group_mod_v1(self,tmp_datapath, port_list, group_weight_list, group_id=_cookie)
                set_switch_for_barrier.add(tmp_datapath)


        #確保剛才group entry 設定完成這樣後面用到group entry的路線才不會錯誤
        for tmp_datapath in set_switch_for_barrier:
            self.wait_finish_switch_BARRIER_finish(tmp_datapath)
        #開始設定除了起點的flow entry
        
        set_switch_for_barrier=set()
        for path, weight in zip(route_path_list, weight_list):
            for i in path[5::3]:
                set_datapath_id = i[0]
                set_out_port = i[1]
                tmp_datapath = GLOBAL_VALUE.G.nodes[(
                    set_datapath_id, None)]["datapath"]
                set_switch_for_barrier.add(tmp_datapath)
                ofp = tmp_datapath.ofproto
                parser = tmp_datapath.ofproto_parser
                match = parser.OFPMatch(
                    eth_type=ether_types.ETH_TYPE_IP, ipv4_dst=dst,ip_dscp=dscp)
                if len(_switch[set_datapath_id].keys()) >= 2:
                    
                    action = [parser.OFPActionGroup(group_id=_cookie)]
                    instruction = [parser.OFPInstructionActions(
                        ofp.OFPIT_APPLY_ACTIONS, action)]
                    mod = parser.OFPFlowMod(datapath=tmp_datapath,
                                            priority=priority, table_id=2,
                                            command=ofp.OFPFC_ADD,
                                            match=match, cookie=_cookie,
                                            instructions=instruction, idle_timeout=idle_timeout,hard_timeout=hard_timeout
                                            )
                    OFPT_FLOW_MOD.send_ADD_FlowMod(mod)
                else:
                   
                    action = [parser.OFPActionOutput(port=set_out_port)]
                    instruction = [parser.OFPInstructionActions(
                        ofp.OFPIT_APPLY_ACTIONS, action)]
                    mod = parser.OFPFlowMod(datapath=tmp_datapath,
                                            priority=priority, table_id=2,
                                            command=ofp.OFPFC_ADD,
                                            match=match, cookie=_cookie,
                                            instructions=instruction, idle_timeout=idle_timeout,hard_timeout=hard_timeout
                                            )
                    OFPT_FLOW_MOD.send_ADD_FlowMod(mod)
        #確保已經設定
        for tmp_datapath in set_switch_for_barrier:
            self.wait_finish_switch_BARRIER_finish(tmp_datapath)
        set_switch_for_barrier=set()
        #全部設定完成 才能開始設定開頭的路線
        for path, weight in zip(route_path_list, weight_list):
            i =path[2]#開頭
            set_datapath_id = i[0]
            set_out_port = i[1]
            tmp_datapath = GLOBAL_VALUE.G.nodes[(
                set_datapath_id, None)]["datapath"]
            set_switch_for_barrier.add(tmp_datapath)
            ofp = tmp_datapath.ofproto
            parser = tmp_datapath.ofproto_parser
            match = parser.OFPMatch(
                eth_type=ether_types.ETH_TYPE_IP, ipv4_dst=dst,ip_dscp=dscp)
            if len(_switch[set_datapath_id].keys()) >= 2:
                action = [parser.OFPActionGroup(group_id=_cookie)]
                instruction = [parser.OFPInstructionActions(
                    ofp.OFPIT_APPLY_ACTIONS, action)]
                mod = parser.OFPFlowMod(datapath=tmp_datapath,
                                        priority=priority, table_id=2,
                                        command=ofp.OFPFC_ADD,
                                        match=match, cookie=_cookie,
                                        instructions=instruction, idle_timeout=idle_timeout,hard_timeout=hard_timeout
                                        )
                OFPT_FLOW_MOD.send_ADD_FlowMod(mod)
            else:
                action = [parser.OFPActionOutput(port=set_out_port)]
                instruction = [parser.OFPInstructionActions(
                    ofp.OFPIT_APPLY_ACTIONS, action)]
                mod = parser.OFPFlowMod(datapath=tmp_datapath,
                                        priority=priority, table_id=2,
                                        command=ofp.OFPFC_ADD,
                                        match=match, cookie=_cookie,
                                        instructions=instruction, idle_timeout=idle_timeout,hard_timeout=hard_timeout
                                        )
                OFPT_FLOW_MOD.send_ADD_FlowMod(mod)
        for tmp_datapath in set_switch_for_barrier:
            self.wait_finish_switch_BARRIER_finish(tmp_datapath)



        # FIXME 這個數值有最大值 需要回收
        GLOBAL_VALUE.PATH[dst][priority]["cookie"]=_cookie
        if GLOBAL_VALUE.PATH[dst][priority]["path"]=={}:
            GLOBAL_VALUE.PATH[dst][priority]["path"]=[]
        if GLOBAL_VALUE.PATH[dst][priority]["weight"]=={}:
            GLOBAL_VALUE.PATH[dst][priority]["weight"]=[]
         
        for p,w in zip(route_path_list,weight_list):
            if p not in GLOBAL_VALUE.PATH[dst][priority]["path"]:
                GLOBAL_VALUE.PATH[dst][priority]["path"].append(p)
                GLOBAL_VALUE.PATH[dst][priority]["weight"].append(w)

         
        if GLOBAL_VALUE.PATH[dst][priority]["graph"]=={}:
            GLOBAL_VALUE.PATH[dst][priority]["graph"]=nx.DiGraph()

        for path in route_path_list:   
            prev_node=None
            for node in path:  
                if prev_node!=None:
                    if GLOBAL_VALUE.PATH[dst][priority]["graph"]=={}:
                        GLOBAL_VALUE.PATH[dst][priority]["graph"]=nx.DiGraph()
                    GLOBAL_VALUE.PATH[dst][priority]["graph"].add_edge(prev_node, node, weight=1)    
                prev_node=node 
        self.setting_multi_route_path_SEM.release()
 
    def _check_know_ip_place(self, ip):
        # 確保此ip位置知道在那
        if GLOBAL_VALUE.ip_get_datapathid_port[ip] == {}:
            # 因為不知道此目的地 ip在哪個交換機的哪個port,所以需要暴力arp到處問
            self._arp_request_all(ip)
            # FIXME 這裡要注意迴圈引發問題 可能需要異步處理,arp只發一次
            # 這裡等待問完的結果
            while GLOBAL_VALUE.ip_get_datapathid_port[ip] == {}:
                hub.sleep(0)
                # time.sleep(0.01)#如果沒有sleep會導致 整個系統停擺,可以有其他寫法？
    # 被動路由
    def check_route_setting(self,src_datapath_id,pkt_ipv4,priority):
        for path in GLOBAL_VALUE.PATH[pkt_ipv4.dst][priority]["path"]:
            i=path[2]
            set_datapath_id = i[0]
            if src_datapath_id==set_datapath_id:
                 
                return True
        return False
    def handle_route(self, datapath, port, msg):
        # 下面這行再做,當不知道ip在哪個port與交換機,就需要利用arp prop序詢問
        print("------------")
        print("被動路由")
        print("\n\n")
        self.route_control_sem.acquire()
        data = msg.data
        in_port = msg.match['in_port']

        pkt = packet.Packet(data=data)
        pkt_ethernet = pkt.get_protocol(ethernet.ethernet)
        pkt_ipv4 = pkt.get_protocol(ipv4.ipv4)
        alog = "low_delay"  # EIGRP
        
        dscp=pkt_ipv4.tos>>2
        priority=(2*dscp)+1
        if dscp==0:
            alog = "low_delay"
        else:
            alog="low_jitter"

        self._check_know_ip_place(pkt_ipv4.src)
        self._check_know_ip_place(pkt_ipv4.dst)
        # 拿出目的地交換機id
        dst_datapath_id = GLOBAL_VALUE.ip_get_datapathid_port[pkt_ipv4.dst]["datapath_id"]
        # 拿出目的地port number
        dst_port = GLOBAL_VALUE.ip_get_datapathid_port[pkt_ipv4.dst]["port"]
        src_datapath_id = GLOBAL_VALUE.ip_get_datapathid_port[pkt_ipv4.src]["datapath_id"]
        # 拿出目的地port number
        src_port = GLOBAL_VALUE.ip_get_datapathid_port[pkt_ipv4.src]["port"]
        #為了避免多個相同src_ip dst_ip pkt_ipv4.tos封包同時處理路由
        #確認是否已經設定完成
        if self.check_route_setting(src_datapath_id,pkt_ipv4,priority):
            tmp_datapath = GLOBAL_VALUE.G.nodes[(src_datapath_id, None)]["datapath"]
            route_module.Packout_to_FlowTable(tmp_datapath,data)
            self.route_control_sem.release()
            return
            
        self.check_route_is_process_SEM.acquire()
        process_route=False
        #print(self.check_route_is_process[pkt_ipv4.dst][pkt_ipv4.tos],pkt_ipv4.dst,pkt_ipv4.tos)
        if self.check_route_is_process[src_datapath_id][pkt_ipv4.dst][pkt_ipv4.tos]=={}:
            #當還沒開始處理從src_datapath_id到pkt_ipv4.dst的qos:pkt_ipv4.tos的路線
            #就搶下來做
            self.check_route_is_process[src_datapath_id][pkt_ipv4.dst][pkt_ipv4.tos]["process"]=True
            process_route=True
            #print(self.check_route_is_process[pkt_ipv4.dst][pkt_ipv4.tos],pkt_ipv4.dst,pkt_ipv4.tos)
        self.check_route_is_process_SEM.release()
        if process_route==False:
            
            #會進來這裡是因為控制器已經在處理這個路由 所以不需要重新處理一次
            #但是交換機一直上來問,等到路徑設定完成才轉送這些
            while self.check_route_setting(src_datapath_id,pkt_ipv4,priority)==False:
                hub.sleep(0)

            tmp_datapath = GLOBAL_VALUE.G.nodes[(src_datapath_id, None)]["datapath"]
            route_module.Packout_to_FlowTable(tmp_datapath,data)
            self.route_control_sem.release()
            return
        #print("有")
        # 選出單一路徑
        prev_G=route_module.Get_NOW_GRAPH(self,pkt_ipv4.dst,priority)
        route_path_list_go,_=route_module.k_shortest_path_loop_free_version(self,4,src_datapath_id,src_port,dst_datapath_id,dst_port,check_G=prev_G)
        weight_list_go = [1 for _ in range(len(route_path_list_go))]
        self.setting_multi_route_path(route_path_list_go, weight_list_go, pkt_ipv4.dst,idle_timeout=10,tos=pkt_ipv4.tos,prev_path=GLOBAL_VALUE.PATH[pkt_ipv4.dst][priority]["path"],prev_weight=GLOBAL_VALUE.PATH[pkt_ipv4.dst][priority]["weight"])
        # 上面只是規劃好路徑 這裡要幫 上來控制器詢問的`迷途小封包` 指引,防止等待rto等等...
        # 你可以測試下面刪除會導致每次pingall都要等待
        # 確保是有找到路徑
        #把送上來未知的封包重新送回去路徑的起始點
        pkt = packet.Packet(data=data)
        tmp_datapath = GLOBAL_VALUE.G.nodes[(src_datapath_id, None)]["datapath"]
        route_module.Packout_to_FlowTable(tmp_datapath,data)
        self.check_route_is_process_SEM.acquire()
        del self.check_route_is_process[src_datapath_id][pkt_ipv4.dst][pkt_ipv4.tos]["process"]
        self.check_route_is_process_SEM.release()



        self.route_control_sem.release()
   
        
    def get_cookie(self,dst,priority):
        # Semaphore(1)
        # 表示一次只能有一個人進來拿cookie
        # 類似mutex lock但是eventlet沒有mutex我就用Semaphore代替
        #self.reuse_cookie={}
        if GLOBAL_VALUE.PATH[dst][priority]["cookie"]!={}:    
            return GLOBAL_VALUE.PATH[dst][priority]["cookie"]
        else:
            self.sem.acquire()
            if len(self.reuse_cookie)==0:
                _cookie = self.cookie  # 保證不會有兩個人拿到相同cookie
                self.cookie = self.cookie+1  # FIXME 這個數值有最大值(2^32-1) 需要回收
                #self.reuse_cookie[_cookie]=True
            else:
                _cookie=list(self.reuse_cookie.keys())[0] 
                del self.reuse_cookie[_cookie]
            GLOBAL_VALUE.PATH[dst][priority]["cookie"]=_cookie
            self.sem.release()
            return _cookie

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
    def active_route2(self):
        #GLOBAL_VALUE.get_cookie()
        time.sleep(15)
        # FIXME 重要要修
        # print(nx.shortest_path(GLOBAL_VALUE.G,(4,2),(2,3),weight="weight"))
        print(GLOBAL_VALUE.ip_get_datapathid_port)

# !SECTION
