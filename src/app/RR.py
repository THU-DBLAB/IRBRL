# 2019
# Authour: Lu-Yi-Hsun
# Using visual code
# https://marketplace.visualstudio.com/items?itemName=ExodiusStudios.comment-anchors
import time
import logging
import networkx as nx
import json
from utils import log, dict_tool
from tui import tui
from route_metrics import formula
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
from ryu.lib.packet import ether_types,in_proto,icmpv6
from ryu.lib.packet import lldp
from ryu.lib.packet import packet
from ryu.utils import hex_array
from ryu.lib import hub
from ryu import cfg
from itertools import islice
CONF = cfg.CONF

# log_file_name="rr.log"
# log.setup_logger(filename=log_file_name, maxBytes=0,backupCount=0, level=logging.DEBUG)

# log.Global_Log[log_file_name].debug('dd ')


class RinformanceRoute(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_5.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        # SECTION __init__
        print("請等拓樸探索完畢")
        # run app_manager.RyuApp oject's __init__()
        super(RinformanceRoute, self).__init__(*args, **kwargs)
        self.MTU = 1500
        # NOTE Openflow Extend setting
        self.OpEPS = 0  # Openflow Extend Port State
        self.OpELD_EtherType = 0x1105  # Openflow Extend Link Detect(int)
        self.OpEQW_EtherType = 0x5157 # Openflow Extend QoS Weight
        self.cookie=0#每條路線都有一個唯一cookie, flow entry的cookie與group_id共用此數字 所以最大值為2^32-1=4294967295
        #handle_arp
        self.ARP_SEND_FROM_CONTROLLER=b'\xff\11'#(bytes)
        # https://www.iana.org/assignments/arp-parameters/arp-parameters.xhtml
        # REQUEST = 1
        # REPLY   = 2
        self.ARP_request = 1
        self.ARP_reply = 2
        self.PATH=nested_dict()
        # self.echo_latency[ev.msg.datapath.id] Detect controller --one way---> switch latency
        self.echo_latency = {}
        
        # self.OpELD_start_time[datapath.id][out_port]
        self.OpELD_start_time = nested_dict()
        self.ARP_Table = {}  # for more hight speed
        self.ip_get_datapathid_port = nested_dict() #

        # self.G.nodes[datapath.id]["port"][in_port]["host"] can get the same data but self.G.nodes
        # NOTE can recognize if OpenVswitch is Edge Switch or not

        # The space of the TUI,for draw data
        self.TUI_Mapping = []
        # init networkx
        self.G = nx.DiGraph()
        
        # NOTE Start Green Thread
        self._handle_route_thread=[]

         
        self._active_route_thread = hub.spawn(self.active_route)
        # NOTE Monitor
        self._monitor_thread = hub.spawn(self._monitor)
        self.delta = 3  # sec,using in _monitor() ,to control update speed
        self._monitor_link_wait = 1
        self._monitor_sent_opedl_packets = 50
        self._monitor_each_opeld_extra_byte = 0  # self.MTU-16#max=
        self._monitor_wait_opeld_back = 2  # sec 超過此時間的封包都會被當作遺失

        # NOTE Text-based user interface(tui)
        #if CONF.RR.TUI:
        #self._run_tui_htread = hub.spawn(self._run_tui)
        #self._update_tui_htread = hub.spawn(self._update_tui)

        # NOTE self.G = nx.DiGraph() Design

        """
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

        self.G.nodes[($datapath.id,None)]   |["datapath"]=<Datapath object>
                                            |["port"]={$port_id:{
                                                        "DSCP_METER_SET_FLAG":True/{},
                                                        "OFPMP_PORT_DESC":
                                                                {"port_no": 1, "length": 72, "hw_addr": "be:f3:b6:8a:f8:1e", "config": 0,"state": 4, "properties": [{"type": 0, "length": 32, "curr": 2112,"advertised": 0, "supported": 0, "peer": 0, "curr_speed": 10000000,"max_speed": 0}], "update_time": 1552314248.2066813
                                                                },
                                                        "OFPMP_PORT_STATS":
                                                                {'length': 304, 'port_no': 2, 'duration_sec': 17, 'duration_nsec': 235000000, 'rx_packets': 11, 'tx_packets': 10, 'rx_bytes': 698, 'tx_bytes': 684, 'rx_dropped': 0, 'tx_dropped': 0, 'rx_errors': 0, 'tx_errors': 0, 'properties': [{'type': 0, 'length': 40, 'rx_frame_err': 0, 'rx_over_err': 0, 'rx_crc_err': 0, 'collisions': 0}, {'type': 65535, 'length': 184, 'experimenter': 43521, 'exp_type': 1, 'data': [
                                                                    0, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295]}], 'update_time': 1553333684.6574402, 'rx_bytes_delta': 14, 'tx_bytes_delta': 14},

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
                                           
        """
        # NOTE EDGES STRUCT SPEC
        # Support Link Aggregation
        # $list_of_port_id1[0]<->$list_of_port_id2[0]
        # $list_of_port_id1[1]<->$list_of_port_id2[1]
        """
        self.G[($datapath.id1,$datapath.port1)][($datapath.id2,$datapath.port2)]|["detect"]|["latency_ms"]:0~max
                                                                                           |["jitter_ms"]:0~max
                                                                                           |["bandwidth_bytes_per_s"]:0~max_bandwidth　重要!!這個代表可用的頻寬
                                                                                           |["loss_percent"]:0~1%
                                                                                |["tmp"][$seq]={"start":timestamp,"end":timestamp}



        """

    #!SECTION
# ────────────────────────────────────────────────────────────────────────────────
    """SECTION For DiGraph
    +-+-+-+ +-+-+-+-+-+-+-+
    |F|o|r| |D|i|G|r|a|p|h|
    +-+-+-+ +-+-+-+-+-+-+-+
    """

    def check_edge_is_link(self, ID1, ID2):
        # if port connect to port ,it return True
        if ID1[1] == None or ID2[1] == None:
            return False
        else:
            return True

    def check_node_is_switch(self, ID):
        # if ID=(datapath_id,None) it mean that node is switch
        if ID[1] == None:
            return True
        else:
            return False
    #!SECTION
# ────────────────────────────────────────────────────────────────────────────────
    """SECTION Green Thread
    +-+-+-+-+-+ +-+-+-+-+-+-+
    |G|r|e|e|n| |T|h|r|e|a|d|
    +-+-+-+-+-+ +-+-+-+-+-+-+
    """
# ────────────────────────────────────────────────────────────────────────────────
    # NOTE Monitor

    def _monitor(self):
        time.sleep(3)
        def decorator_node_iteration(func):
            def node_iteration():
                while True:
                    for node_id in self.G.copy().nodes:
                        if self.check_node_is_switch(node_id):
                            datapath = self.G.nodes[node_id]["datapath"]
                            func(datapath)
                    time.sleep(self.delta)
            return node_iteration

        @decorator_node_iteration
        def _sent_echo(datapath):
            self.send_echo_request(datapath)

        @decorator_node_iteration
        def _update_switch(datapath):
            self.send_port_stats_request(datapath)
            self.send_port_desc_stats_request(datapath)
        # @decorator_node_iteration
        def _update_link():
            def clear_link_tmp_data():
                for edge in list(self.G.edges()):
                    edge_id1 = edge[0]
                    edge_id2 = edge[1]
                    if self.check_edge_is_link(edge_id1, edge_id2):
                        # self.G[start_switch][end_switch]["port"][end_switch]
                        link_data = self.G[edge_id1][edge_id2]
                        link_data["tmp"] = nested_dict()
            def sent_opeld_to_all_port():
                for node_id in self.G.copy().nodes:
                    if self.check_node_is_switch(node_id):
                        switch_data = self.G.nodes[node_id]
                        #
                        switch_data=switch_data.copy()
                        for port_no in switch_data["port"].keys():
                            # if the port can working
                            if switch_data["port"][port_no]["OFPMP_PORT_DESC"]["state"] == ofproto_v1_5.OFPPS_LIVE:
                                    self.send_opeld_packet(
                                        switch_data["datapath"], port_no, extra_byte=self._monitor_each_opeld_extra_byte, num_packets=self._monitor_sent_opedl_packets)
            while True:
                # NOTE start
                # print(self.G.nodes[datapath.id]["port"][1]["OFPMP_PORT_DESC"]["properties"],datapath.id)
                clear_link_tmp_data()#重算所有統計
                # sent opeld to all port of each switch for doing link detect and topology detect
                sent_opeld_to_all_port()#發送封包
                # wait for packet back
                time.sleep(self._monitor_wait_opeld_back)
                # print(self.G[2][1]["tmp"])
                # print(self.G[2][1]["port"])
                for edge in list(self.G.edges()):
                    edge_id1 = edge[0]
                    edge_id2 = edge[1]
                    if self.check_edge_is_link(edge_id1, edge_id2):
                        start_switch = (edge_id1[0],None)
                        start_port_number = edge_id1[1]
                        end_switch = (edge_id2[0],None)
                        end_port_number = edge_id2[1]
                        # print(self.G[start_switch][end_switch]["tmp"])
                        packet_start_time = []
                        packet_end_time = []
                        seq_packet = self.G[edge_id1][edge_id2]["tmp"]
                        get_packets_number = len(seq_packet.keys())
                        # latency
                        for seq in seq_packet.keys():
                            packet_start_time.append(
                                seq_packet[seq]["start"])
                            packet_end_time.append(seq_packet[seq]["end"])
                        latency = []
                        for s_t, e_t in zip(packet_start_time, packet_end_time):
                            latency.append(e_t-s_t)
                        
                        #all_t = max(packet_end_time)-min(packet_start_time)
                        # jitter

                        if len(packet_end_time)!=0 or len(packet_start_time)!=0:
                        
                            curr_speed = min(int(self.G.nodes[start_switch]["port"][start_port_number]["OFPMP_PORT_DESC"]["properties"][0]["curr_speed"]), int(
                                self.G.nodes[end_switch]["port"][end_port_number]["OFPMP_PORT_DESC"]["properties"][0]["curr_speed"]))  # curr_speed kbps

                            tx_bytes_delta = int(
                                self.G.nodes[start_switch]["port"][start_port_number]["OFPMP_PORT_STATS"]["tx_bytes_delta"])
                            
                            jitter = abs(np.std(latency) * 1000)  # millisecond
                            # A. S. Tanenbaum and D. J. Wetherall, Computer Networks, 5th ed. Upper Saddle River, NJ, USA: Prentice Hall Press, 2010.
                            # "The variation (i.e., standard deviation) in the delay or packet arrival times is called jitter."
                            # default one packet from A TO B latency millisecond(ms)
                            delay_one_packet = abs(np.mean(latency)*1000)
                            loss = 1-(get_packets_number /
                                        self._monitor_sent_opedl_packets)
                            # bytes_s=(get_packets_number*(self._monitor_each_opeld_extra_byte+16))/all_t

                            # available using bandwith bytes per second
                            # curr_speed is kbps
                            bw = ((1000*curr_speed)/8) - \
                                (tx_bytes_delta/self.delta)
                            # print(start_switch,end_switch,link_index,"jitter",jitter,"delay_one_packet",delay_one_packet,"loss",loss,"gbytes_s",bw)

                            # millisecond
                            self.G[edge_id1][edge_id2]["detect"]["jitter_ms"] = jitter
                            # %how many percent of the packet loss
                            self.G[edge_id1][edge_id2]["detect"]["loss_percent"] = loss
                            # available bandwidth
                            self.G[edge_id1][edge_id2]["detect"]["bandwidth_bytes_per_s"] = bw
                            # from a to b ,just one way ,millisecond
                            self.G[edge_id1][edge_id2]["detect"]["latency_ms"] = delay_one_packet


                            #這裡你可以自創演算法去評估權重
                            self.G[edge_id1][edge_id2]["weight"] = formula.OSPF(bw*8)
                            self.G[edge_id1][edge_id2]["hop"] = 1
                            self.G[edge_id1][edge_id2]["EIGRP"] = formula.EIGRP((bw*8)/1000,curr_speed,tx_bytes_delta,delay_one_packet,loss)
                            #FIXME 新增演算法 路線 取最小的頻寬 當最佳

                             
                                
                            #print(nx.shortest_path(self.G,(1,None),(2,None),weight="weight"),nx.shortest_path_length(self.G,(1,None),(2,None),weight="weight"))
                            #try:
                                #print(list(islice(nx.shortest_simple_paths(self.G, (1,None), (2,None), weight="weight"), 2)))
                            #except:
                            #   pass
        # print("ok")
        self._sent_echo_thread = hub.spawn(_sent_echo)
        self._update_switch_thread = hub.spawn(_update_switch)
        self._update_link_thread = hub.spawn(_update_link)

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
            for node_id in self.G.copy().nodes:
                if self.check_node_is_switch(node_id):
                    switch_title = Mapping_idx
                    Mapping_idx += 1
                    if_EDGE_SWITCH = ""
                    for port in self.G.copy().nodes[node_id]["port"].keys():
                        host = self.G.nodes[node_id]["port"][port]["host"]
                        if host != {}:
                            if_EDGE_SWITCH = "Edge Switch"
                        stats = self.G.nodes[node_id]["port"][port]["OFPMP_PORT_STATS"]
                        desc = self.G.nodes[node_id]["port"][port]["OFPMP_PORT_DESC"]
                        line = "★ port"+str(port)+" state "+str(desc["state"])+" duration_sec "+str(stats["duration_sec"])+" rx_bytes "+str(stats["rx_bytes"])+" tx_bytes "+str(
                            stats["tx_bytes"])+" rx_bytes_delta "+str(stats["rx_bytes_delta"])+" tx_bytes_delta "+str(stats["tx_bytes_delta"])+" host "+str(host)
                        self.TUI_Mapping[Mapping_idx] = line
                        Mapping_idx += 1

                    line = "datapath ID"+str(node_id)+" "+if_EDGE_SWITCH
                    self.TUI_Mapping[switch_title] = line
                    line = "all_port_duration_s " + \
                        str(self.G.nodes[node_id]["all_port_duration_s"])
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
                    for table_id in self.G.copy().nodes[node_id]["FLOW_TABLE"]:
                        for priority in self.G.copy().nodes[node_id]["FLOW_TABLE"][table_id]:
                            for match in self.G.copy().nodes[node_id]["FLOW_TABLE"][table_id][priority]:
                                self.TUI_Mapping[Mapping_idx] = "table_id: "+str(table_id)+" priority: "+str(priority)+" match: "+str(match)
                                Mapping_idx += 1
                    
            self.TUI_Mapping[Mapping_idx] = "Topology Link"
            Mapping_idx += 1
            # self.TUI_Mapping[Mapping_idx]=str(self.G.edges())
            #print(self.G.edges())
            for edge in list(self.G.edges()):
                edge_id1 = edge[0]
                edge_id2 = edge[1]
                if self.check_edge_is_link(edge_id1, edge_id2):
                    # self.G[start_switch][end_switch]["port"][end_switch]
                    ed = self.G[edge_id1][edge_id2]
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
                    #print(link_data)
                    self.TUI_Mapping[Mapping_idx] = link_data
                    Mapping_idx += 1
  #              self.G[start_switch][end_switch]["detect"][link_index]["jitter_ms"]=jitter#millisecond
   #             self.G[start_switch][end_switch]["detect"][link_index]["loss_percent"]=loss#%how many percent of the packet loss
    #            self.G[start_switch][end_switch]["detect"][link_index]["bandwidth_bytes_per_s"]=bw#
     #           self.G[start_switch][end_switch]["detect"][link_index]["latency_ms"]=delay_one_packet#from a to b ,just one way ,millisecond
      #          self.G[start_switch][end_switch]["weight"]=formula.OSPF(bw*8)
            


            
            for i in range(30):
                self.TUI_Mapping[Mapping_idx] = ""
                Mapping_idx += 1

            time.sleep(1)

            # self.TUI_Mapping[1]="duration_sec"+str(self.G.nodes[1]["port"][1]["OFPMP_PORT_STATS"]["duration_sec"])
    # NOTE Run tui
    def _run_tui(self):
        tui.Screen(self.TUI_Mapping)
    # !SECTION
# ────────────────────────────────────────────────────────────────────────────────
    """ SECTION Openflow Switch Protocol
     +-+-+-+-+-+-+-+-+ +-+-+-+-+-+-+ +-+-+-+-+-+-+-+-+
     |O|p|e|n|F|l|o|w| |S|w|i|t|c|h| |P|r|o|t|o|c|o|l|
     +-+-+-+-+-+-+-+-+ +-+-+-+-+-+-+ +-+-+-+-+-+-+-+-+
    """
# ────────────────────────────────────────────────────────────────────────────────

    # NOTE: OFPT_FEATURES_REPLY
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def _switch_features_handler(self, ev):
        def init_node():
            node_id = (datapath.id, None)
            if not self.G.has_node(node_id):
                self.G.add_node(node_id)
                self.G.nodes[node_id]["datapath"] = datapath
                self.G.nodes[node_id]["port"] = nested_dict()
                self.G.nodes[node_id]["all_port_duration_s_temp"] = 0
                self.G.nodes[node_id]["all_port_duration_s"] = 0
                self.G.nodes[node_id]["FLOW_TABLE"] = nested_dict()
                self.G.nodes[node_id]["now_max_group_id"] = 0
                self.G.nodes[node_id]["now_max_xid"] = 0#這個是在傳送openflow協定的時候標示的xid,當發生錯誤的時候交換機會回傳同個xid,讓我們知道剛剛哪個傳送的openflow發生錯誤
         
            #set_meter_table is in _port_desc_stats_reply_handler
            #FIXME EDGE SWITCH AND TRANSIT SWITCH flow table 1 NOT ADD YET
        def set_flow_table_0_control_and_except():
            #Control and exception handling packets 
            #set_flow_table_0_DSCP() is in _port_desc_stats_reply_handler
            self.control_and_except(datapath,eth_type=self.OpELD_EtherType)
            self.control_and_except(datapath,eth_type=self.OpEQW_EtherType)
            self.control_and_except(datapath,eth_type=ether_types.ETH_TYPE_ARP)
            self.control_and_except(datapath,eth_type=ether_types.ETH_TYPE_IPV6,ip_proto=in_proto.IPPROTO_ICMPV6,icmpv6_type=icmpv6.ND_NEIGHBOR_SOLICIT)
            self.add_all_flow_to_table(datapath,0,1)
        def set_flow_table_1():
            self.add_all_flow_to_table(datapath,1,2)

        def set_flow_table_2():
            #FIXME 關於未知封包,可以嘗試實做buffer  max_len 或是buffer_id能加速? 請參考opnflow1.51-7.2.6.1 Output Action Structures
            self.unknow_route_ask_controller(datapath)
        msg = ev.msg
        datapath = msg.datapath
        self.send_port_desc_stats_request(datapath)
        init_node()
        

        set_flow_table_0_control_and_except()
        set_flow_table_1()
        set_flow_table_2()
    # NOTE init G nodes


# ────────────────────────────────────────────────────────────────────────────────
    """ SECTION Multipart Messages
     +-+-+-+-+-+-+-+-+-+ +-+-+-+-+-+-+-+-+
     |M|u|l|t|i|p|a|r|t| |M|e|s|s|a|g|e|s|
     +-+-+-+-+-+-+-+-+-+ +-+-+-+-+-+-+-+-+
    """
# ────────────────────────────────────────────────────────────────────────────────

    # SECTION OFPMP_PORT_STATS TYPE_ID:4
    def send_port_stats_request(self, datapath):
        """[summary]

        Args:
            datapath ([type]): [description]
        """
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser
        req = ofp_parser.OFPPortStatsRequest(datapath, 0, ofp.OFPP_ANY)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofp = datapath.ofproto
        all_port_duration_s_temp = self.G.nodes[(
            datapath.id, None)]["all_port_duration_s_temp"]
        # get the list of "close port"
        close_port = list(self.G.nodes[(datapath.id, None)]["port"].keys())
        all_port_duration_s=0
        for OFPPortStats in ev.msg.body:
            if OFPPortStats.port_no < ofp.OFPP_MAX:
                # OFPPortStats is a "class",so it need to covent to dict
                
                data = dict_tool.class2dict(OFPPortStats)

                data["update_time"] = time.time()

                # for short cut
                OFPMP_PORT_STATS = self.G.nodes[(
                    datapath.id, None)]["port"][OFPPortStats.port_no]["OFPMP_PORT_STATS"]
                # get tx/rx bytes delta  data["rx/tx_bytes_delta"]
                if isinstance(OFPMP_PORT_STATS["tx_bytes"], int):
                    tx_bytes_prev = OFPMP_PORT_STATS["tx_bytes"]
                else:
                    tx_bytes_prev = 0

                if isinstance(OFPMP_PORT_STATS["rx_bytes"], int):
                    rx_bytes_prev = OFPMP_PORT_STATS["rx_bytes"]
                else:
                    rx_bytes_prev = 0
                data["rx_bytes_delta"] = int(
                    data["rx_bytes"])-int(rx_bytes_prev)
                data["tx_bytes_delta"] = int(
                    data["tx_bytes"])-int(tx_bytes_prev)

                # update data
                self.G.nodes[(
                    datapath.id, None)]["port"][OFPPortStats.port_no]["OFPMP_PORT_STATS"] = data
                # count all_port_duration_s
                all_port_duration_s = all_port_duration_s_temp + \
                    data["duration_sec"]

                close_port.remove(OFPPortStats.port_no)
        self.G.nodes[(datapath.id, None)
                      ]["all_port_duration_s"] = all_port_duration_s

        # clear close port delta
        for close in close_port:
            self.G.nodes[(datapath.id, None)
                          ]["port"][close]["OFPMP_PORT_STATS"]["rx_bytes_delta"] = 0
            self.G.nodes[(datapath.id, None)
                          ]["port"][close]["OFPMP_PORT_STATS"]["tx_bytes_delta"] = 0
            pass


    # !SECTION

    # SECTION OFPMP_PORT_DESC TYPE_ID:13
    def send_port_desc_stats_request(self, datapath):
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser
        req = ofp_parser.OFPPortDescStatsRequest(datapath, 0, ofp.OFPP_ANY)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPPortDescStatsReply, MAIN_DISPATCHER)
    def _port_desc_stats_reply_handler(self, ev):
        def set_meter_table(inport_num,curr_speed):
            #curr_speed max speed of the port
            #conbin inport(24bit) and id(8bit) to 32bit
                           
            for priority,rate_per in zip(range(0,7),range(4,11)):
                meter_id=int(bin(inport_num)[2:].zfill(24)+bin(priority)[2:].zfill(8),2)
                 
                percent= rate_per/10 #40%~100%
                self.add_meter(datapath,meter_id,int(percent*curr_speed))
       
        def set_flow_table_0_DSCP(inport_num):
                #datapath,dscp,IPVx,table_id,meter_id
                #dscp:
                #0b000 000=0
                #0b001 000=8
                #0b010 000=16
                #0b011 000=24
                #dscp=8*meter_id
                for priority in range(7):
                    #IPV4
                    meter_id=int(bin(inport_num)[2:].zfill(24)+bin(priority)[2:].zfill(8),2)
                    self.DSCP_flow(datapath,inport_num,8*priority,ether_types.ETH_TYPE_IP,1,meter_id)
                    #IPV6
                    self.DSCP_flow(datapath,inport_num,8*priority,ether_types.ETH_TYPE_IPV6,1,meter_id)
        """build this
                 weight=0
                 +----+
        switch_id|    |port_id
        +--------+    +--------+
        |(1,None)|    | (1,22) |
        +--------+    +--------+
          Node   |    ^   Node
                 +----+
                 weight=0
        """
        def init_port_node(datapath,port_no):
            switch_id=(datapath.id,None)
            port_id=(datapath.id,port_no)
            if not self.G.has_node(port_id):
                self.G.add_node(port_id)
            if not self.G.has_edge(switch_id,port_id):
                self.G.add_edge(switch_id,port_id,weight=0)
            if not self.G.has_edge(port_id,switch_id):  
                self.G.add_edge(port_id,switch_id,weight=0)
        msg = ev.msg
        datapath = msg.datapath
        ofp = datapath.ofproto
        for OFPPort in ev.msg.body:
            if OFPPort.port_no < ofp.OFPP_MAX:
                # check it have been set or not
                #data var format
                """{"port_no": 1, "length": 72, "hw_addr": "be:f3:b6:8a:f8:1e", "config": 0,"state": 4, "properties": [{"type": 0, "length": 32, "curr": 2112,"advertised": 0, "supported": 0, "peer": 0, "curr_speed": 10000000,"max_speed": 0}], "update_time": 1552314248.2066813
                }"""
                data = dict_tool.class2dict(OFPPort)
                data["update_time"] = time.time()
                self.G.nodes[(datapath.id,None)]["port"][OFPPort.port_no]["DSCP&Meter_SET_FLAG"]=True
                self.G.nodes[(datapath.id,None)]["port"][OFPPort.port_no]["OFPMP_PORT_DESC"] = data
                init_port_node(datapath,OFPPort.port_no)

                DSCP_METER_SET_FLAG=self.G.nodes[(datapath.id,None)]["port"][OFPPort.port_no]["DSCP_METER_SET_FLAG"]
                if DSCP_METER_SET_FLAG!=True:
                    curr_speed=data["properties"][0]["curr_speed"]
                   
                    set_meter_table(OFPPort.port_no,curr_speed)
                    set_flow_table_0_DSCP(OFPPort.port_no)
                    self.G.nodes[(datapath.id,None)]["port"][OFPPort.port_no]["DSCP_METER_SET_FLAG"]=True


        # print(datapath.id,(self.G.nodes[datapath.id]["port"]),type(self.G.nodes[datapath.id]["port"][OFPPort.port_no]["OFPMP_PORT_DESC"]))
    # !SECTION
    # !SECTION

# ────────────────────────────────────────────────────────────────────────────────
    """SECTION Modify State Messages
     +-+-+-+-+-+-+ +-+-+-+-+-+ +-+-+-+-+-+-+-+-+
     |M|o|d|i|f|y| |S|t|a|t|e| |M|e|s|s|a|g|e|s|
     +-+-+-+-+-+-+ +-+-+-+-+-+ +-+-+-+-+-+-+-+-+
    """
# ────────────────────────────────────────────────────────────────────────────────

    # SECTION Modify Flow Entry Message
    
    """
    mod type is  <class 'ryu.ofproto.ofproto_v1_5_parser.OFPFlowMod'>

    mod.__dict__ can get this 
    {'datapath': <ryu.controller.controller.Datapath object at 0x7f6f7bf78b10>, 'version': None, 'msg_type': None, 'msg_len': None, 'xid': None, 'buf': None, 'cookie': 0, 'cookie_mask': 0, 'table_id': 0, 'command': 0, 'idle_timeout': 0, 'hard_timeout': 0, 'priority': 1, 'buffer_id': 4294967295, 'out_port': 0, 'out_group': 0, 'flags': 0, 'importance': 0, 'match': OFPMatch(oxm_fields={'in_port': 321, 'eth_type': 34525, 'ip_dscp': 40}), 'instructions': [OFPInstructionActions(actions=[OFPActionMeter(len=8,meter_id=82181,type=29)],type=4), OFPInstructionGotoTable(len=8,table_id=1,type=1)]}
    
    兩個flow entry同match,table id,priority代表重疊
    Two flow entries overlap if a single packet may match both, and both flow entries have the same priority-(6.4 Flow Table Modification Messages)

    """

    def _send_ADD_FlowMod(self,mod):
        datapath=mod.datapath
        OFPFlowMod=mod.__dict__ 
        table_id=OFPFlowMod["table_id"]
        match=OFPFlowMod["match"]
        priority=OFPFlowMod["priority"]
        ofp = datapath.ofproto
        #要交換機當flow entry被刪除都要通知控制器
        mod.flags=ofp.OFPFF_SEND_FLOW_REM
        #if self._check_no_overlap_on_server(datapath.id,table_id,priority,match):
        mod.xid=self.G.nodes[(datapath.id,None)]["now_max_xid"]
        self.G.nodes[(datapath.id,None)]["now_max_xid"]=self.G.nodes[(datapath.id,None)]["now_max_xid"]+1
        self.G.nodes[(datapath.id,None)]["FLOW_TABLE"][table_id][priority][str(match)]=mod

        datapath.send_msg(mod)
        #    return True
        return False
    def _check_no_overlap_on_server(self,datapath_id,table_id,priority,match):
        return  True if len(self.G.nodes[(datapath_id,None)]["FLOW_TABLE"][table_id][priority][str(match)])==0 else False
        
     

    def add_all_flow_to_table(self, datapath,from_table_id,to_table_id):
        ofp = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        inst = [parser.OFPInstructionGotoTable(to_table_id)]
        mod = parser.OFPFlowMod(datapath=datapath, table_id=from_table_id,priority=0,
                                command=ofp.OFPFC_ADD, match=match, instructions=inst)
        
        self._send_ADD_FlowMod(mod)

    def drop_all(self, datapath):
        ofp = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch()
        instruction = [
            parser.OFPInstructionActions(ofp.OFPIT_CLEAR_ACTIONS, [])
        ]
        mod = parser.OFPFlowMod(datapath=datapath,
                                priority=0,
                                command=ofp.OFPFC_ADD,
                                match=match,
                                instructions=instruction
                                )
        self._send_ADD_FlowMod(mod)

    def add_lldp_flow(self, datapath):
        ofp = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_LLDP)
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER)]
        self.add_flow(datapath, 1, match, actions)

    def add_flow(self, datapath, priority, match, actions):
        ofp = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                command=ofp.OFPFC_ADD, match=match, instructions=inst)
        self._send_ADD_FlowMod(mod)
    def DSCP_flow(self,datapath,in_port,dscp,IPVx,table_id,meter_id):
        #IPVx=ether_types.ETH_TYPE_IPV6/ether_types.ETH_TYPE_IP
        ofp = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch(in_port=in_port,eth_type=IPVx,ip_dscp=dscp)
        action=[parser.OFPActionMeter(meter_id=meter_id)]
        instruction = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, action), parser.OFPInstructionGotoTable(1)]
        
        mod = parser.OFPFlowMod(datapath=datapath,
                                priority=1,
                                command=ofp.OFPFC_ADD,
                                match=match,
                                instructions=instruction,hard_timeout=3
                                )
        self._send_ADD_FlowMod(mod)
    def unknow_route_ask_controller(self,datapath):
        ofp = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER)] 
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=0,table_id=2,
                                command=ofp.OFPFC_ADD, match=match, instructions=inst,hard_timeout=0)
        self._send_ADD_FlowMod(mod)

    def control_and_except(self,datapath,**kwargs):
        ofp = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch(**kwargs)
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER)] 
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=65535,
                                command=ofp.OFPFC_ADD, match=match, instructions=inst,hard_timeout=0)
        self._send_ADD_FlowMod(mod)
        
    # !SECTION
    # SECTION Meter Modification Message Modifications
    def add_meter(self,datapath,meter_id,rate):
        #reat kb/s (kilo-bit per second)
        ofp = datapath.ofproto
        parser = datapath.ofproto_parser
        bands = [parser.OFPMeterBandDrop(type_=ofp.OFPMBT_DROP, len_=0, rate=rate, burst_size=10)]
        msg=parser.OFPMeterMod(datapath=datapath, command=ofp.OFPMC_ADD, flags=ofp.OFPMF_KBPS, meter_id=meter_id, bands=bands)
        datapath.send_msg(msg)
    # !SECTION 
    # !SECTION
# ────────────────────────────────────────────────────────────────────────────────
    """SECTION Packet-Out Message
     +-+-+-+-+-+-+-+-+-+-+ +-+-+-+-+-+-+-+
     |P|a|c|k|e|t|-|O|u|t| |M|e|s|s|a|g|e|
     +-+-+-+-+-+-+-+-+-+-+ +-+-+-+-+-+-+-+
    """
# ────────────────────────────────────────────────────────────────────────────────
    # NOTE Openflow Extend Link Detect(OpELD)
    # uint64_t datapath_id OF1.5 SPEC
    # uint32_t port_no OF1.5 SPEC
    # uint16_t eth_type=0X1105,or self.OpELD_EtherType
    # uint16_t: Sequence Number(SEQ)
    """
     0                   1                   2                   3  
     0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |                                                               |
    +                        datapath_id(64bits)                    +
    |                                                               |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |                          port_no(32bits)                      |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    |         eth_type(16bits)    |           SEQ(16bits)           |
    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
    """

    def decode_opeld(self, dst_mac, src_mac):
        datapath_id_mac = dst_mac+":"+src_mac[0:5]
        port_no = src_mac[6:]
        return int(datapath_id_mac.replace(":", ""), 16), int(port_no.replace(":", ""), 16)

    def encode_opeld(self, datapath_id, out_port):
        def hex_to_mac(mac_hex):
            return ":".join(mac_hex[i:i+2] for i in range(0, len(mac_hex), 2))
        dst_hex = "{:016x}".format(datapath_id)[0:12]

        src_hex = "{:016x}".format(datapath_id)[12:]+"{:08x}".format(out_port)
        return hex_to_mac(dst_hex), hex_to_mac(src_hex)

    def send_opeld_packet(self, datapath, out_port, extra_byte=0, num_packets=1):
        # datapath_id(8bytes)+port_no(4bytes)+eth_type(2bytes)
        opeld_header_size = 14# bytes
        SEQ_size = 2  # bytes
        min_opeld_size = opeld_header_size+SEQ_size
        ofp = datapath.ofproto
        parser = datapath.ofproto_parser
        pkt = packet.Packet()
        dst, src = self.encode_opeld(datapath.id, out_port)
        pkt.add_protocol(ethernet.ethernet(
            ethertype=self.OpELD_EtherType, dst=dst, src=src))
        pkt.serialize()
        # default MTU Max is 1500
        if not 0 <= extra_byte <= self.MTU-min_opeld_size:
            log.Global_Log[log_file_name].warning('extra_byte out of size')
            # max(min(maxn, n), minn)
            extra_byte = max(min(self.MTU-min_opeld_size, extra_byte), 0)

        opeld_header = pkt.data[0:opeld_header_size]

        match = datapath.ofproto_parser.OFPMatch(in_port=ofp.OFPP_CONTROLLER)
        actions = [parser.OFPActionOutput(port=out_port)]

        if not 1 <= num_packets:
            num_packets = max(num_packets, 1)  # max(min(maxn, n), minn)

        # update start time

        for seq in range(num_packets):
            self.OpELD_start_time[datapath.id][out_port][seq] = time.time()
            SEQ = (seq).to_bytes(SEQ_size, byteorder="big")

            opeld_packet = opeld_header+SEQ+bytearray(extra_byte)
            out = parser.OFPPacketOut(datapath=datapath, buffer_id=ofp.OFP_NO_BUFFER,
                                      match=match, actions=actions, data=opeld_packet)
            datapath.send_msg(out)

        for k in self.OpELD_start_time[datapath.id][out_port].keys():
            if k >= num_packets:
                del self.OpELD_start_time[datapath.id][out_port][k]


# ────────────────────────────────────────────────────────────────────────────────
    # NOTE send_arp_packet


    def send_arp_packet(self, datapath, out_port,eth_src_mac,eth_dst_mac, arp_opcode, arp_src_mac, arp_src_ip, arp_dst_mac, arp_dst_ip,payload):
        """opcode:1 request"""
        """opcode:2 reply"""
        ofp = datapath.ofproto
        in_port=ofp.OFPP_CONTROLLER
        parser = datapath.ofproto_parser
        pkt = packet.Packet()
        pkt.add_protocol(ethernet.ethernet(
            ethertype=ether_types.ETH_TYPE_ARP, src=eth_src_mac,dst=eth_dst_mac))
        pkt.add_protocol(arp.arp(opcode=arp_opcode, src_mac=arp_src_mac,
                                 src_ip=arp_src_ip, dst_mac=arp_dst_mac, dst_ip=arp_dst_ip))
        pkt.serialize()
        data = pkt.data+payload
        match = datapath.ofproto_parser.OFPMatch(in_port=in_port)
        actions = [parser.OFPActionOutput(port=out_port)]

        out = parser.OFPPacketOut(datapath=datapath, buffer_id=ofp.OFP_NO_BUFFER,
                                  match=match, actions=actions, data=data)
        datapath.send_msg(out)
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
        dp = msg.datapath
        ofp = dp.ofproto
        #print(type(msg.match))
        #print(self.G.nodes[(int(dp.id),None)]["FLOW_TABLE"])
        try:
            del self.G.nodes[(dp.id,None)]["FLOW_TABLE"][int(msg.table_id)][int(msg.priority)][str(msg.match)]
        except:
            return
            pass
        if msg.reason == ofp.OFPRR_IDLE_TIMEOUT:
            reason = 'IDLE TIMEOUT'
        elif msg.reason == ofp.OFPRR_HARD_TIMEOUT:
            reason = 'HARD TIMEOUT'
        elif msg.reason == ofp.OFPRR_DELETE:
            reason = 'DELETE'
        elif msg.reason == ofp.OFPRR_GROUP_DELETE:
            reason = 'GROUP DELETE'
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
        #print(data)
        self.G.nodes[(datapath.id,None)]["port"][msg.desc.port_no]["OFPMP_PORT_DESC"] = data
        if msg.reason == ofp.OFPPR_ADD:
            """ADD"""
            pass

        elif msg.reason == ofp.OFPPR_DELETE:
            """DELETE"""

            # doing storage all_port_duration_s_temp
            try:
                self.G.nodes[(datapath.id,None)]["all_port_duration_s_temp"] = int(self.G.nodes[(datapath.id,None)]["all_port_duration_s_temp"])+int(
                    self.G.nodes[(datapath.id,None)]["port"][msg.desc.port_no]["OFPMP_PORT_STATS"]["duration_sec"])
            except:
                self.G.nodes[(datapath.id,None)]["all_port_duration_s_temp"] = 0

            # NOTE Openflow Extend Port State
            # difference with OF1.5 ofp_port_state
            # Implementation add this to port state "0",define the port have been ""DELETE"" by OVSDB
            # data["state"]
            # Openflow Extend Port State= 0 ,sort name:OPEPS /*the port have been ""DELETE"" */
            # OFPPS_LINK_DOWN = 1, /* No physical link present. */
            # OFPPS_BLOCKED = 2, /* Port is blocked */
            # OFPPS_LIVE = 4, /* Live for Fast Failover Group. */
            #data["state"] = self.OpEPS
            self.G.nodes[(datapath.id,None)]["port"][msg.desc.port_no]["OFPMP_PORT_DESC"] = data
        elif msg.reason == ofp.OFPPR_MODIFY:
            """MODIFY"""
            if ofp_port_state == ofp.OFPPS_LINK_DOWN:
                """OFPPS_LINK_DOWN"""
                pass
            elif ofp_port_state == ofp.OFPPS_BLOCKED:
                """OFPPS_BLOCKED"""
                pass
                # del self.G.nodes[datapath.id]["port"][msg.desc.port_no]
            elif ofp_port_state == ofp.OFPPS_LIVE:
                """OFPPS_LIVE"""
                pass
                # self.G.nodes[datapath.id]["port"].update(msg.desc.port_no)
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
        msg = ev.msg
        datapath = msg.datapath
        port = msg.match['in_port']
        pkt = packet.Packet(data=msg.data)
        pkt_ethernet = pkt.get_protocol(ethernet.ethernet)
        if pkt_ethernet:
            if pkt_ethernet.ethertype == self.OpELD_EtherType:
                # print("get",self.decode_eth_1105(pkt_ethernet.dst,pkt_ethernet.src))
                seq = int.from_bytes(msg.data[14:16], "big")
                self.handle_opeld(datapath, port, pkt_ethernet, seq)
        else:
            # TODO LOG ERROR
            return

        pkt_icmp = pkt.get_protocol(icmp.icmp)
        if pkt_icmp:
            print("icmp!!!")
            pass

        pkt_arp = pkt.get_protocol(arp.arp)
        if pkt_arp:
            #print("問")
            self.handle_arp(datapath, pkt_arp, port,msg.data)

        pkt_lldp = pkt.get_protocol(lldp.lldp)
        if pkt_lldp:
            self.handle_lldp(datapath, port, pkt_ethernet, pkt_lldp)
        pkt_ipv4 = pkt.get_protocol(ipv4.ipv4)
        if pkt_ipv4:
            print("想路由")

            #交換機想要透過ipv4路由但不知道路,我們需要幫它
            self._handle_route_thread.append(hub.spawn(self.handle_route,datapath=datapath,port=port,pkt_ipv4=pkt_ipv4,data=msg.data))
            print("thr!!")
     
    #被動模塊
    def handle_route_v2(self,datapath, port, pkt_ipv4,data):
         
        #print(datapath, port, pkt_ipv4,self.ip_get_datapathid_port[pkt_ipv4.dst])
        if self.ip_get_datapathid_port[pkt_ipv4.dst]!={}:#確保知道目的地在哪裡
            dst_datapath_id=self.ip_get_datapathid_port[pkt_ipv4.dst]["datapath_id"]
            dst_port=self.ip_get_datapathid_port[pkt_ipv4.dst]["port"]
            #選出單一路徑
            #去
            alog="weight"#EIGRP
            route_path_go=nx.shortest_path(self.G,(datapath.id,port),(dst_datapath_id,dst_port),weight=alog)
            self.setting_route_path(route_path_go,pkt_ipv4.dst)
            #回
            route_path_back=nx.shortest_path(self.G,(dst_datapath_id,dst_port),(datapath.id,port),weight=alog)
            self.setting_route_path(route_path_back,pkt_ipv4.src)
            #上面只是規劃好路徑 這裡要幫 上來控制器詢問的`迷途小封包` 指引,防止等待rto等等...
            #你可以測試下面刪除會導致每次pingall都要等待
            ofp = datapath.ofproto
            parser = datapath.ofproto_parser
            match = datapath.ofproto_parser.OFPMatch(in_port=port)
            out_port=route_path_go[2][1]
            actions = [parser.OFPActionOutput(port=out_port)]
            out = parser.OFPPacketOut(datapath=datapath, buffer_id=ofp.OFP_NO_BUFFER,
                                    match=match, actions=actions, data=data)
            datapath.send_msg(out)
            #                       route_path[2::3]
            #[(1, 1), (1, None), (1, 2), (2, 2), (2, None), (2, 1)]
            #                     ^^^^                       ^^^^
             
            #多路徑k sort path
            #islice(nx.shortest_simple_paths(self.G, (1,None), (2,None), weight="weight"), 2)

    def _arp_request_all(self,dst_ip):
        #暴力搜尋dst_ip的mac為多少:目的維護arp與了解到底哪個ip在哪個port這樣才能路由
        for node_id in self.G.copy().nodes:
            if self.check_node_is_switch(node_id):
                switch_data = self.G.nodes[node_id]
                for port_no in switch_data["port"].keys():
                    # if the port can working
                    if switch_data["port"][port_no]["OFPMP_PORT_DESC"]["state"] == ofproto_v1_5.OFPPS_LIVE: 
                        #arp_src_ip="0.0.0.0"這種是ARP probe型態的封包
                        #An ARP Probe with an all-zero 'sender IP address' -rfc5227 [Page 6]
                        self.send_arp_packet(datapath=switch_data["datapath"], out_port=port_no,eth_src_mac='00:00:00:00:00:00',eth_dst_mac="ff:ff:ff:ff:ff:ff", arp_opcode=self.ARP_request,
                                arp_src_mac='00:00:00:00:00:00', arp_src_ip="0.0.0.0", arp_dst_mac='00:00:00:00:00:00', arp_dst_ip=dst_ip,payload=self.ARP_SEND_FROM_CONTROLLER)
            
        
    def handle_arp(self, datapath, pkt_arp, in_port,packet):
        def update_fome_arp_data(datapath,pkt_arp,in_port):
            #FIXME 
            self.G.nodes[(datapath.id,None)]["port"][in_port]["host"][pkt_arp.src_ip] = pkt_arp.src_mac
            self.ARP_Table[pkt_arp.src_ip] = pkt_arp.src_mac
            self.ip_get_datapathid_port[pkt_arp.src_ip]["datapath_id"]=datapath.id
            self.ip_get_datapathid_port[pkt_arp.src_ip]["port"]=in_port

        #避免廣播風暴會拒絕最後2個bytes==ARP_SEND_FROM_CONTROLLER
        last_two_bytes=packet[-2:]
        #reject and do not process the arp packet ask from controller
        if last_two_bytes==self.ARP_SEND_FROM_CONTROLLER:
            return

        ofp = datapath.ofproto
         
        if in_port < ofp.OFPP_MAX:
            if pkt_arp.opcode == self.ARP_request:
                update_fome_arp_data(datapath,pkt_arp,in_port)
                if pkt_arp.dst_ip in self.ARP_Table:
                    self.send_arp_packet(datapath=datapath, out_port=in_port,eth_src_mac=self.ARP_Table[pkt_arp.dst_ip],eth_dst_mac=pkt_arp.src_mac, arp_opcode=self.ARP_reply,
                                         arp_src_mac=self.ARP_Table[pkt_arp.dst_ip], arp_src_ip=pkt_arp.dst_ip, arp_dst_mac=pkt_arp.src_mac, arp_dst_ip=pkt_arp.src_ip,payload=self.ARP_SEND_FROM_CONTROLLER)
                else:
                    #TODO : send to all switch all port to check!
                    self._arp_request_all(pkt_arp.dst_ip)     
                    pass
            elif pkt_arp.opcode == self.ARP_reply:
                print("回答")
                print(pkt_arp)
                update_fome_arp_data(datapath,pkt_arp,in_port)
                 
            else:
                # TODO HADLE EXPECTION
                pass

        # Openflow Extend Link Detect(OpELD) Topology/Link Detect

    # SECTION handle_opeld
    def handle_opeld(self, datapath, port, pkt_opeld, seq):
        # NOTE Topology maintain
        def init_edge(start_node_id, end_node_id):
            print("拓樸",start_node_id, end_node_id)
            self.G.add_edge(start_node_id, end_node_id)
            self.G[start_node_id][end_node_id]["tmp"] = nested_dict()
            self.G[start_node_id][end_node_id]["detect"] = nested_dict()

        

        start_switch, start_port = self.decode_opeld(
            pkt_opeld.dst, pkt_opeld.src)
        end_switch = datapath.id
        end_port = port
        start_node_id=(start_switch,start_port)
        end_node_id=(end_switch,end_port)
        # NOTE Topology setting
        if not self.G.has_edge(start_node_id, end_node_id):
            init_edge(start_node_id ,end_node_id)
        # NOTE Link Detect
        # Link delay
        # http://www.cnsm-conf.org/2013/documents/papers/CNSM/p122-phemius.pdf
        """
                       C0
                     ------
                    |      |
                    T1    T2
                    |      |
                H0--S0-T3-S1--H1
        """
        try:

            if seq in self.OpELD_start_time[start_switch][start_port]:
                start_time = self.OpELD_start_time[start_switch][start_port][seq]
                end_time = time.time()
                
                start_switch_latency = self.echo_latency[start_switch]
                end_switch_latency = self.echo_latency[end_switch]
                # negative beacuse start_switch_latency+end_switch_latency>(time.time()-start_time)

                self.G[start_node_id][end_node_id]["tmp"][seq]["start"] = start_time + \
                    start_switch_latency
                self.G[start_node_id][end_node_id]["tmp"][seq]["end"] = end_time - \
                    end_switch_latency
        except:
            # FIXME :!!!!
            pass

        # TODO !!!!!!!!!!!!!!!!!!!!!!!!!
    # !SECTION

    # NOTE handle_lldp

    def handle_lldp(self, datapath, port, pkt_ethernet, pkt_lldp):
        start_switch = pkt_lldp.tlvs[0].chassis_id
        start_port = pkt_lldp.tlvs[1].port_id
        end_switch = datapath.id
        end_port = port

        """
        self.G.add_edge(start_switch, end_switch)
        T1 = self.echo_latency[int(datapath.id)]/2
        T2 = self.echo_latency[int(pkt_lldp.tlvs[0].chassis_id)]/2
        Totol = time.time() - \
            self.echo_delay[int(datapath.id), int(port)]["start"]

        print(datapath.id, port,
              pkt_lldp.tlvs[1].port_id, pkt_lldp.tlvs[0].chassis_id)
        print("T3", (Totol-T1-T2)*1000, "ms", "Totol", Totol*1000, "ms")
        print("T1", T1*1000, "ms", "T2", T2*1000, "ms")
        print("----------------------")"""
    # !SECTION

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

    # SECTION Echo
    # NOTE CONTROLLER--"echo_request"->SWITCH
    def send_echo_request(self, datapath):
        ofp_parser = datapath.ofproto_parser
        echo_req = ofp_parser.OFPEchoRequest(datapath,
                                             data=b"%.12f" % time.time())
        datapath.send_msg(echo_req)

    # NOTE  SWITCH--"echo_request"->CONTROLLER
    # this like heart beat for switch to check if controller is live
    @set_ev_cls(ofp_event.EventOFPEchoRequest, [HANDSHAKE_DISPATCHER, CONFIG_DISPATCHER, MAIN_DISPATCHER])
    def _echo_request_handler(self, ev):
        pass
        # print('OFPEchoRequest received: data=%s',(ev.msg.data))

    def send_echo_reply(self, datapath, data):
        ofp_parser = datapath.ofproto_parser

        reply = ofp_parser.OFPEchoReply(datapath, data)
        datapath.send_msg(reply)

    @set_ev_cls(ofp_event.EventOFPEchoReply, [HANDSHAKE_DISPATCHER, CONFIG_DISPATCHER, MAIN_DISPATCHER])
    def _echo_reply_handler(self, ev):
        # print('OFPEchoRequest received2: data=%s',(ev.msg.data))
        # self.echo_latency[]
        now_timestamp = time.time()
        try:
            # Round-trip delay time
            latency = now_timestamp - float(ev.msg.data)
            self.echo_latency[ev.msg.datapath.id] = latency / \
                2  # End-to-end delay
        except:
            return

        # print('EventOFPEchoReply received: data=%s',(latency*1000))

    # !SECTION
    # NOTE EventOFPErrorMsg

    @set_ev_cls(ofp_event.EventOFPErrorMsg, [HANDSHAKE_DISPATCHER, CONFIG_DISPATCHER, MAIN_DISPATCHER])
    def error_msg_handler(self, ev):
        print(ev)
        msg = ev.msg
        datapath=msg.datapath
        ofproto = msg.datapath.ofproto
        if msg.type==ofproto.OFPET_FLOW_MOD_FAILED:
            #這裡就是要設定flow entry但是失敗了 所以需要刪除
            #因為dict做迴圈都需要複製,防止執行時突然被新插入導致迴圈會錯亂拉QQ
            _G=self.G.copy()
            _FLOW_TABLE=_G.nodes[(datapath.id,None)]["FLOW_TABLE"]
            for table_id in _FLOW_TABLE:
                for priority in _FLOW_TABLE[table_id]:
                    for match in _FLOW_TABLE[table_id][priority]:
                        mod=_FLOW_TABLE[table_id][priority][match]
                        #抓到了你這個flow entry設定錯誤 要刪除紀錄喔
                        if mod.xid==msg.xid:
                            del self.G.nodes[(datapath.id,None)]["FLOW_TABLE"][table_id][priority][match]

        elif msg.type==ofproto.OFPET_GROUP_MOD_FAILED:
            pass
            print("修修我")

        print("OFPErrorMsg received:",msg.type, msg.code,msg.xid)
        """print('OFPErrorMsg received: type=0x%02x code=0x%02x message=%s',
              msg.type, msg.code, (msg.data))"""

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
    def send_group_mod(self, datapath):
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser
        port = 1
        max_len = 2000
        actions = [ofp_parser.OFPActionOutput(port, max_len)]
        weight = 100
        watch_port = 0
        watch_group = 0
        buckets = [ofp_parser.OFPBucket(weight, watch_port, watch_group,
                                        actions)]
        group_id = 1
        command_bucket_id=1
        req = ofp_parser.OFPGroupMod(datapath, ofp.OFPGC_ADD,
                                    ofp.OFPGT_SELECT, group_id,
                                    command_bucket_id, buckets)
        datapath.send_msg(req)


    def send_add_group_mod(self, datapath,port_list:list,weight_list:list,group_id:int):
        """
        group_id是給flow entry指引要導到哪個group entry
        """
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser
        buckets=[]
        #Each bucket of the group must have an unique Bucket ID-openflow1.51-p115 所以亂給個id給它 反正我沒用到
        bucket_id=0
        for port,weight in zip(port_list,weight_list):
            #bucket_id=self.G.nodes[(datapath.id,None)]["now_max_group_id"]
            actions = [ofp_parser.OFPActionOutput(port)]
            #spec openflow1.5.1 p.116  struct ofp_group_bucket_prop_weight
            #注意ryu ofv1.5.1的group範例寫錯
            #下面這個寫法要靠自己挖ryu原始碼才寫出來,所以遇到問題盡量挖控制器ryu,openvswitch原始碼
            #ofp_bucket->properties->ofp_group_bucket_prop_weight-spec openflow1.5.1 p.115~p.116 
            _weight=ofp_parser.OFPGroupBucketPropWeight(weight=weight,type_=ofp.OFPGBPT_WEIGHT)
            
            buckets.append(ofp_parser.OFPBucket(bucket_id=bucket_id,actions=actions,properties=[_weight]))
            bucket_id=bucket_id+1
            self.G.nodes[(datapath.id,None)]["now_max_group_id"]=self.G.nodes[(datapath.id,None)]["now_max_group_id"]+1
        #從多個路線根據權重(weight)隨機從buckets選一個OFPBucket(ofp.OFPGT_SELECT),OFPBucket裡面就放要actions要出去哪個port
        mod = ofp_parser.OFPGroupMod(datapath, command=ofp.OFPGC_ADD,
                                    type_=ofp.OFPGT_SELECT, group_id=group_id, buckets=buckets)
         
        
        mod.xid=self.G.nodes[(datapath.id,None)]["now_max_xid"]
        self.G.nodes[(datapath.id,None)]["now_max_xid"]=self.G.nodes[(datapath.id,None)]["now_max_xid"]+1
        datapath.send_msg(mod)

    def send_delete_group_mod(self, datapath,group_id:int):
        """
        group_id是給flow entry指引要導到哪個group entry
        

        """
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser
        #從多個路線根據權重(weight)隨機選一個走(ofp.OFPGT_SELECT)
        req = ofp_parser.OFPGroupMod(datapath, ofp.OFPGC_DELETE, ofp.OFPG_ALL,group_id=group_id)
        datapath.send_msg(req)

    def delete_route_path(self,route_path,cookie):
        for i in route_path[-1::-3]:
            #刪除flow entry根據cookie
            set_datapath_id=i[0]
            tmp_datapath=self.G.nodes[(set_datapath_id,None)]["datapath"]
            ofp = tmp_datapath.ofproto
            parser = tmp_datapath.ofproto_parser
            match = parser.OFPMatch()
            #刪除交換機內所有數值為cookie的flow entry
            mod = parser.OFPFlowMod(datapath=tmp_datapath,
                                    priority=1,table_id=ofp.OFPTT_ALL,
                                    command=ofp.OFPFC_DELETE,out_port=ofp.OFPP_ANY,out_group=ofp.OFPG_ANY,
                                    match=match,cookie=cookie,cookie_mask=0xffffffffffffffff
                                    )
            tmp_datapath.send_msg(mod)
            #接下來刪除group id-不一定會有group但是我一起刪看看
            self.send_delete_group_mod(tmp_datapath,cookie)
            #route_path
    def setting_single_route_path(self,route_path,dst,src=None):
        #這裡是專門設定singal path 沒有group table介入
        #OFPMatch沒有設定src的好處可以節省flow entry,壞處是有可能發生環形路由不容易控制,該怎麼減少flow entry?需要相關論文
        #route_path=[(2, 3), (2, None), (2, 2), (3, 3), (3, None), (3, 4)]
        #抽象route_path解說
        #src在交換機2的3號port(2, 3)->2交換機(2, None)->2交換機的2號port(2, 2)->3號交換機的3號port(3, 3)->3號交換機(3, None)->3號交換機的4號port(3, 4)到達dst
        
        
        #設定路徑從後面開始 從(3, 4)到(2, 2) 因為如果一開始就設定前面路線的flow entry封包會開始流動結果後面跟不上設定就開始遺失
        for i in route_path[-1::-3]:
            set_datapath_id=i[0]
            set_out_port=i[1]
            tmp_datapath=self.G.nodes[(set_datapath_id,None)]["datapath"]
            ofp = tmp_datapath.ofproto
            parser = tmp_datapath.ofproto_parser
            match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP,ipv4_dst=dst,ipv4_src=src)
            action = [parser.OFPActionOutput(port=set_out_port)]
            instruction = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, action)]
            mod = parser.OFPFlowMod(datapath=tmp_datapath,
                                    priority=1,table_id=2,
                                    command=ofp.OFPFC_ADD,
                                    match=match,cookie=self.cookie,
                                    instructions=instruction,idle_timeout=60
                                    )
            self._send_ADD_FlowMod(mod)
            self.cookie=self.cookie+1
             
             
    def setting_multi_route_path(self,route_path_list,dst,src):
        #多條路徑(route_path_list)結合每個路徑的權重(weight_list)
        for i in route_path_list[-1::-3]:
            set_datapath_id=i[0]
            set_out_port=i[1]
            tmp_datapath=self.G.nodes[(set_datapath_id,None)]["datapath"]
            ofp = tmp_datapath.ofproto
            parser = tmp_datapath.ofproto_parser
            match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP,ipv4_dst=dst,ipv4_src=src)
            action = [parser.OFPActionGroup(group_id=self.cookie)]
            instruction = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, action)]
            mod = parser.OFPFlowMod(datapath=tmp_datapath,
                                    priority=1,table_id=2,
                                    command=ofp.OFPFC_ADD,
                                    match=match,cookie=self.cookie,
                                    instructions=instruction,idle_timeout=1
                                    )
            self.send_add_group_mod(tmp_datapath,[set_out_port,1],[10,0],self.cookie)
            self._send_ADD_FlowMod(mod)
        self.cookie=self.cookie+1
        self.PATH[src][dst][self.cookie]=route_path_list
        print("setting")
            #route_path

    
    def _check_know_ip_place(self,ip):
        #確保此ip位置知道在那
        if self.ip_get_datapathid_port[ip]=={}:
            #因為不知道此目的地 ip在哪個交換機的哪個port,所以需要暴力arp到處問
            self._arp_request_all(ip)
            #FIXME 這裡要注意迴圈引發問題 可能需要異步處理
            #這裡等待問完的結果
            while self.ip_get_datapathid_port[ip]=={}:
                time.sleep(0.01)#如果沒有sleep會導致 整個系統停擺,可以有其他寫法？
    #被動路由
    def handle_route(self,datapath, port, pkt_ipv4,data):

        #下面這行再做,當不知道ip在哪個port與交換機,就需要利用arp prop序詢問 
        self._check_know_ip_place(pkt_ipv4.src)
        self._check_know_ip_place(pkt_ipv4.dst)

        #拿出目的地交換機id
        dst_datapath_id=self.ip_get_datapathid_port[pkt_ipv4.dst]["datapath_id"]
        #拿出目的地port number
        dst_port=self.ip_get_datapathid_port[pkt_ipv4.dst]["port"]

        src_datapath_id=self.ip_get_datapathid_port[pkt_ipv4.src]["datapath_id"]
        #拿出目的地port number
        src_port=self.ip_get_datapathid_port[pkt_ipv4.src]["port"]

        #選出單一路徑
        #你能選擇使用哪套演算法參數,這個是你可以自己寫的,要怎寫請問我拉 
        alog="weight"#EIGRP
        #路徑需要 去回
        #去
        route_path_go=nx.shortest_path(self.G,(src_datapath_id,src_port),(dst_datapath_id,dst_port),weight=alog)
        """
        """
        print("k short")
        print(list(islice(nx.shortest_simple_paths(self.G,(src_datapath_id,src_port),(dst_datapath_id,dst_port), weight="weight"), 4)))
        print("k short")
        self.setting_single_route_path(route_path_go,pkt_ipv4.dst,pkt_ipv4.src)
        #回
        route_path_back=nx.shortest_path(self.G,(dst_datapath_id,dst_port),(src_datapath_id,src_port),weight=alog)
        self.setting_single_route_path(route_path_back,pkt_ipv4.src,pkt_ipv4.dst)
        
        #上面只是規劃好路徑 這裡要幫 上來控制器詢問的`迷途小封包` 指引,防止等待rto等等...
        #你可以測試下面刪除會導致每次pingall都要等待
            
        out_port=route_path_go[2][1]
        #確保是有找到路徑
        if isinstance(out_port, int): 
            tmp_datapath=self.G.nodes[(src_datapath_id,None)]["datapath"]
            ofp = tmp_datapath.ofproto
            parser = tmp_datapath.ofproto_parser
            match = tmp_datapath.ofproto_parser.OFPMatch(in_port=ofp.OFPP_CONTROLLER)
            actions = [parser.OFPActionOutput(port=out_port)]
            out = parser.OFPPacketOut(datapath=tmp_datapath, buffer_id=ofp.OFP_NO_BUFFER,
                                    match=match, actions=actions, data=data)
            tmp_datapath.send_msg(out)
            print(route_path_go,self.G)
        else:
            #保佑不會發生
            print(route_path_go)
            print(datapath.id,port)
            print(pkt_ipv4)
            print(data)
            print(dst_datapath_id,dst_port)
            print(self.ip_get_datapathid_port)
            exit(1)

 
    def active_route(self):
        time.sleep(15)
        #FIXME 重要要修
        #print(nx.shortest_path(self.G,(4,2),(2,3),weight="weight"))
        print(self.ip_get_datapathid_port)
        
# !SECTION  


