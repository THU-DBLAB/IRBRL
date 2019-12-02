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

#RYU
from ryu.base import app_manager
from ryu.ofproto import ofproto_v1_5
# for RYU decorator doing catch Event
from ryu.controller.handler import set_ev_cls
from ryu.controller.handler import HANDSHAKE_DISPATCHER, CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller import ofp_event
from ryu.lib.packet import ethernet, arp, icmp, ipv4
from ryu.lib.packet import ether_types
from ryu.lib.packet import lldp
from ryu.lib.packet import packet
from ryu.lib import hub
from ryu import cfg
CONF = cfg.CONF

#log_file_name="rr.log"
#log.setup_logger(filename=log_file_name, maxBytes=0,backupCount=0, level=logging.DEBUG)

#log.Global_Log[log_file_name].debug('dd ')
 

class RinformanceRoute(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_5.OFP_VERSION]
     

    def __init__(self, *args, **kwargs):
        #SECTION __init__
        super(RinformanceRoute, self).__init__(*args, **kwargs)#run app_manager.RyuApp oject's __init__()
        self.MTU = 1500
        #NOTE Openflow Extend setting
        self.OpEPS=0#Openflow Extend Port State
        self.OpELD_EtherType=0x1105#Openflow Extend Link Detect

 
        self.echo_latency = {}  # self.echo_latency[ev.msg.datapath.id] Detect controller --one way---> switch latency
        self.OpELD_start_time=nested_dict()#self.OpELD_start_time[datapath.id][out_port]
        self.ARP_Table = {}  # for more hight speed
        # self.G.nodes[datapath.id]["port"][in_port]["host"] can get the same data but self.G.nodes
        # NOTE can recognize if OpenVswitch is Edge Switch or not
        
        #The space of the TUI,for draw data
        self.TUI_Mapping = []
        # init networkx
        self.G = nx.DiGraph()

        # NOTE Start Green Thread
        #monitor_evt = hub.Event()

        self._monitor_thread = hub.spawn(self._monitor)
        self.delta = 3  # sec,using in _monitor() ,to control update speed
        self._monitor_link_wait=1
        self.sent_opedl_packets=20
        self.each_opeld_extra_byte=0#self.MTU-16#max=
        self.wait_opeld_back=2#sec
         
        # NOTE Text-based user interface(tui)
        if CONF.RR.TUI:
            self._run_tui_htread = hub.spawn(self._run_tui)
            self._update_tui_htread = hub.spawn(self._update_tui)

        # NOTE self.G = nx.DiGraph() Design
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

        self.G.nodes[$datapath.id] |["datapath"]=<Datapath object>
                                   |["port"]={$port_id:{"OFPMP_PORT_DESC":
                                                            {"port_no": 1, "length": 72, "hw_addr": "be:f3:b6:8a:f8:1e", "config": 0,"state": 4, "properties": [{"type": 0, "length": 32, "curr": 2112,"advertised": 0, "supported": 0, "peer": 0, "curr_speed": 10000000,"max_speed": 0}], "update_time": 1552314248.2066813
                                                            },
                                                       "OFPMP_PORT_STATS":
                                                            {'length': 304, 'port_no': 2, 'duration_sec': 17, 'duration_nsec': 235000000, 'rx_packets': 11, 'tx_packets': 10, 'rx_bytes': 698, 'tx_bytes': 684, 'rx_dropped': 0, 'tx_dropped': 0, 'rx_errors': 0, 'tx_errors': 0, 'properties': [{'type': 0, 'length': 40, 'rx_frame_err': 0, 'rx_over_err': 0, 'rx_crc_err': 0, 'collisions': 0}, {'type': 65535, 'length': 184, 'experimenter': 43521, 'exp_type': 1, 'data': [0, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295]}], 'update_time': 1553333684.6574402, 'rx_bytes_delta': 14, 'tx_bytes_delta': 14},
                                                            
                                                       "host":{[ip address]:[mac adress]}#for ARP table
                                                       }
                                             }
                                   |["all_port_duration_s"]=<class 'int'>     #sec 'active working duration of all port '
                                   |["all_port_duration_s_temp"]=<class 'int'>#temp when del the port, a new port restart,    #OFPMP_PORT_STATS's duration_sec will be zero
                                                 
                                                
        """
        # NOTE EDGES STRUCT SPEC
        # Support Link Aggregation
        # $list_of_port_id1[0]<->$list_of_port_id2[0]
        # $list_of_port_id1[1]<->$list_of_port_id2[1]
        """
        self.G[$datapath.id1][$datapath.id2]|["port"]={
                                            |          [$datapath.id1]=$list_of_port_id1<class 'list'> #$datapath.id1->$list_of_port_id1->$list_of_port_id2->$datapath.id2
                                            |          [$datapath.id2]=$list_of_port_id2<class 'list'> #$datapath.id2->$list_of_port_id2->$list_of_port_id1->$datapath.id1
                                            |           }
                                            |      
                                            |# TODO :HERE NEED DOING!!!!!!!!!!!!!!!!!! 
                                            |["detect"][$link_index]={
                                                                        "latency_ms":2,
                                                                        "jitter_ms":2,
                                                                        "bandwidth_bytes_per_s":23.
                                                                        "loss_percent":0~1%
                                                                          
                                                                    }  
                                            #link_index:lint aggregation 
                                            #$seq:num_packets
                                            |["tmp"][$link_index][$seq]=1.3#sec is could be negative       
 
        
        
        """

        
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
                    for datapath_id in self.G.nodes:
                        datapath = self.G.nodes[datapath_id]["datapath"]
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
        
        
        #@decorator_node_iteration
        def _update_link():
            
            def clear_edge_tmp_data():
                for edge in list(self.G.edges()):
                    datapath1 = 0
                    datapath2 = 1
                    # self.G[start_switch][end_switch]["port"][end_switch]
                    ed = self.G[edge[datapath1]][edge[datapath2]]
                    for link_aggregation in ed["tmp"].keys():
                        ed["tmp"][link_aggregation]=nested_dict()
            
            def sent_opeld_to_all_port():
                 
                for datapath_id in self.G.nodes:
                    datapath = self.G.nodes[datapath_id]["datapath"]
                    for port_no in self.G.nodes[datapath.id]["port"].keys():
                    #if the port can working
                        if self.G.nodes[datapath.id]["port"][port_no]["OFPMP_PORT_DESC"]["state"]==ofproto_v1_5.OFPPS_LIVE:
                            self.send_opeld_packet(datapath, port_no,extra_byte=self.each_opeld_extra_byte,num_packets=self.sent_opedl_packets)
                            
            
            while True:
                #NOTE start
                #print(self.G.nodes[datapath.id]["port"][1]["OFPMP_PORT_DESC"]["properties"],datapath.id)
                clear_edge_tmp_data()
            
                #sent opeld to all port of each switch for doing link detect and topology detect
                sent_opeld_to_all_port()
                
                #wait for packet back
                time.sleep(self.wait_opeld_back)
                
                try:
                    pass
                    #print(self.G[2][1]["tmp"])
                    #print(self.G[2][1]["port"])
                    
                    for edge in list(self.G.edges()):
                        start_switch=edge[0]
                        end_switch=edge[1]
                        #print(self.G[start_switch][end_switch]["tmp"])
                

                        for link_index in self.G[start_switch][end_switch]["tmp"].keys():
                            packet_start_time=[]
                            packet_end_time=[]
                            seq_packet=self.G[start_switch][end_switch]["tmp"][link_index]
                            get_packets_number=len(seq_packet.keys())
                            #latency
                            for seq in seq_packet.keys():
                                packet_start_time.append(seq_packet[seq]["start"])
                                packet_end_time.append(seq_packet[seq]["end"])
                            latency=[]
                            for s_t, e_t in zip(packet_start_time, packet_end_time):
                                latency.append(e_t-s_t)

                            all_t=max(packet_end_time)-min(packet_start_time)
                            #jitter

                            start_port_number=self.G[start_switch][end_switch]["port"][start_switch][link_index]
                            end_port_number=self.G[start_switch][end_switch]["port"][end_switch][link_index]
                            curr_speed=min(int(self.G.nodes[start_switch]["port"][start_port_number]["OFPMP_PORT_DESC"]["properties"][0]["curr_speed"]),int(self.G.nodes[end_switch]["port"][end_port_number]["OFPMP_PORT_DESC"]["properties"][0]["curr_speed"]))#curr_speed kbps
                            tx_bytes_delta=int(self.G.nodes[start_switch]["port"][start_port_number]["OFPMP_PORT_STATS"]["tx_bytes_delta"])
                             
                            jitter=abs(np.std(latency) *1000)#millisecond
                            #A. S. Tanenbaum and D. J. Wetherall, Computer Networks, 5th ed. Upper Saddle River, NJ, USA: Prentice Hall Press, 2010.
                            #"The variation (i.e., standard deviation) in the delay or packet arrival times is called jitter."
            
                            delay_one_packet=abs(np.mean(latency)*1000)#default one packet from A TO B latency millisecond(ms)
                            loss=1-(get_packets_number/self.sent_opedl_packets)
                            #bytes_s=(get_packets_number*(self.each_opeld_extra_byte+16))/all_t
                       
                            
                            bw=((1000*curr_speed)/8) - (tx_bytes_delta/self.delta)#available using bandwith bytes per second
                            #print(start_switch,end_switch,link_index,"jitter",jitter,"delay_one_packet",delay_one_packet,"loss",loss,"gbytes_s",bw)
                           
                            self.G[start_switch][end_switch]["detect"][link_index]["jitter_ms"]=jitter#millisecond
                            self.G[start_switch][end_switch]["detect"][link_index]["loss_percent"]=loss#%how many percent of the packet loss
                            self.G[start_switch][end_switch]["detect"][link_index]["bandwidth_bytes_per_s"]=bw#
                            self.G[start_switch][end_switch]["detect"][link_index]["latency_ms"]=delay_one_packet#from a to b ,just one way ,millisecond
                            self.G[start_switch][end_switch]["weight"]=formula.OSPF(bw*8)
                        #print("loss",1- len(self.G[2][1]["tmp"][0].keys())/self.npp) 
                        
                        #if (1- len(self.G[2][1]["tmp"][0].keys())/self.npp)==0:
                        #   self.npp=self.npp*2
                except:
                    pass     
                     

        #print("ok")
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
        MAX_TUI_LINE=300
        for idx, i in enumerate(title.split("\n")):
            self.TUI_Mapping.append(i)
            Mapping_idx = idx
        for i in range(MAX_TUI_LINE):
            self.TUI_Mapping.append("")
        Mapping_start = Mapping_idx+1
        while True:
            Mapping_idx = Mapping_start
            for node in self.G.nodes:
                switch_title = Mapping_idx
                Mapping_idx += 1
                if_EDGE_SWITCH = ""
                for port in self.G.nodes[node]["port"].keys():
                    host = self.G.nodes[node]["port"][port]["host"]
                    if host != {}:
                        if_EDGE_SWITCH = "Edge Switch"
                    stats = self.G.nodes[node]["port"][port]["OFPMP_PORT_STATS"]
                    desc = self.G.nodes[node]["port"][port]["OFPMP_PORT_DESC"]
                    line = "★ port"+str(port)+" state "+str(desc["state"])+" duration_sec "+str(stats["duration_sec"])+" rx_bytes "+str(stats["rx_bytes"])+" tx_bytes "+str(
                        stats["tx_bytes"])+" rx_bytes_delta "+str(stats["rx_bytes_delta"])+" tx_bytes_delta "+str(stats["tx_bytes_delta"])+" host "+str(host)
                    self.TUI_Mapping[Mapping_idx] = line
                    Mapping_idx += 1

                line = "datapath ID"+str(node)+" "+if_EDGE_SWITCH
                self.TUI_Mapping[switch_title] = line
                line = "all_port_duration_s " + \
                    str(self.G.nodes[node]["all_port_duration_s"])
                self.TUI_Mapping[Mapping_idx] = line

                """
                'duration_sec': 26664, 'duration_nsec': 862000000, 'rx_packets': 22, 'tx_packets': 19
                5, 'rx_bytes': 1636, 'tx_bytes': 12016, 'rx_dropped': 0, 'tx_dropped': 0, 'rx_errors': 0, 'tx_errors': 0
                """
                Mapping_idx += 1
                self.TUI_Mapping[Mapping_idx] = ""
                Mapping_idx += 1

            self.TUI_Mapping[Mapping_idx] = "Topology Link"
            Mapping_idx += 1
            # self.TUI_Mapping[Mapping_idx]=str(self.G.edges())
            for edge in list(self.G.edges()):
                datapath1 = 0
                datapath2 = 1
                edge_data = []
                # self.G[start_switch][end_switch]["port"][end_switch]
                ed = self.G[edge[datapath1]][edge[datapath2]]

                for dpid in ed["port"].keys():
                    edge_data.append("datapath ID "+str(dpid) +
                                     " port_no "+str(ed["port"][dpid]))
                edge_data = edge_data[0]+" ---> "+edge_data[1]
                 

                self.TUI_Mapping[Mapping_idx] = edge_data
                Mapping_idx += 1

                link_data=""
                for link_index in ed["detect"].keys():
                    jitter_ms=str(ed["detect"][link_index]["jitter_ms"])
                    loss_percent=str(ed["detect"][link_index]["loss_percent"])
                    bandwidth_bytes_per_s=str(ed["detect"][link_index]["bandwidth_bytes_per_s"])
                    latency_ms=str(ed["detect"][link_index]["latency_ms"])

                    link_data="link_index:"+str(link_index)+" "+"loss_percent:"+loss_percent+" "+"bandwidth_bytes_per_s:"+bandwidth_bytes_per_s+" "+"latency_ms:"+latency_ms
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

    #NOTE: OFPT_FEATURES_REPLY
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def _switch_features_handler(self, ev):
        def init_node(datapath):
            self.G.add_node(datapath.id)
            self.G.nodes[datapath.id]["datapath"] = datapath
            self.G.nodes[datapath.id]["port"] = nested_dict()
            self.G.nodes[datapath.id]["all_port_duration_s_temp"] = 0
            self.G.nodes[datapath.id]["all_port_duration_s"] = 0

        def init_start_new_switch(datapath):
            # if all flow entry not compare ,it need to ask controller
            self.add_all_flow(datapath)
            # ask switch for their ports
            self.send_port_desc_stats_request(datapath)

        msg = ev.msg
        datapath = msg.datapath
        init_node(datapath)
        init_start_new_switch(datapath)

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
        all_port_duration_s = self.G.nodes[datapath.id]["all_port_duration_s_temp"]
        # get the list of "close port"
        close_port = list(self.G.nodes[datapath.id]["port"].keys())
        for OFPPortStats in ev.msg.body:
            if OFPPortStats.port_no < ofp.OFPP_MAX:
                # OFPPortStats is a "class",so it need to covent to dict
                data = dict_tool.class2dict(OFPPortStats)

                data["update_time"] = time.time()

                # for short cut
                OFPMP_PORT_STATS = self.G.nodes[datapath.id]["port"][OFPPortStats.port_no]["OFPMP_PORT_STATS"]
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
                self.G.nodes[datapath.id]["port"][OFPPortStats.port_no]["OFPMP_PORT_STATS"] = data
                # count all_port_duration_s
                all_port_duration_s = all_port_duration_s+data["duration_sec"]

                close_port.remove(OFPPortStats.port_no)
        self.G.nodes[datapath.id]["all_port_duration_s"] = all_port_duration_s

        # clear close port delta
        for close in close_port:
            self.G.nodes[datapath.id]["port"][close]["OFPMP_PORT_STATS"]["rx_bytes_delta"] = 0
            self.G.nodes[datapath.id]["port"][close]["OFPMP_PORT_STATS"]["tx_bytes_delta"] = 0
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
        msg = ev.msg
        datapath = msg.datapath
        ofp = datapath.ofproto
        for OFPPort in ev.msg.body:
            if OFPPort.port_no < ofp.OFPP_MAX:
                data = dict_tool.class2dict(OFPPort)
                data["update_time"] = time.time()
                self.G.nodes[datapath.id]["port"][OFPPort.port_no]["OFPMP_PORT_DESC"] = data
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
    def add_all_flow(self, datapath):
        ofp = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER)]
        self.add_flow(datapath, 0, match, actions)

    def drop_all(self, datapath):
        ofp = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch()
        instruction = [
            parser.OFPInstructionActions(ofp.OFPIT_CLEAR_ACTIONS, [])
        ]
        msg = parser.OFPFlowMod(datapath=datapath,
                                priority=0,
                                command=ofp.OFPFC_ADD,
                                match=match,
                                instructions=instruction
                                )
        datapath.send_msg(msg)

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
        datapath.send_msg(mod)
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
     
    def send_opeld_packet(self, datapath, out_port, extra_byte=0,num_packets=1):
        opeld_header_size = 14  # datapath_id(8bytes)+port_no(4bytes)+eth_type(2bytes)
        SEQ_size=2#bytes
        min_opeld_size=opeld_header_size+SEQ_size
        ofp = datapath.ofproto
        parser = datapath.ofproto_parser
        pkt = packet.Packet()
        dst, src = self.encode_opeld(datapath.id, out_port)
        pkt.add_protocol(ethernet.ethernet(ethertype=self.OpELD_EtherType, dst=dst, src=src))
        pkt.serialize()
        # default MTU Max is 1500
        if not 0 <= extra_byte <= self.MTU-min_opeld_size:
            log.Global_Log[log_file_name].warning('extra_byte out of size')
            extra_byte=max(min(self.MTU-min_opeld_size, extra_byte), 0)#max(min(maxn, n), minn)

        opeld_header = pkt.data[0:opeld_header_size] 

        match = datapath.ofproto_parser.OFPMatch(in_port=ofp.OFPP_CONTROLLER)
        actions = [parser.OFPActionOutput(port=out_port)]

    
        if not 1 <= num_packets:
            num_packets=max(num_packets, 1)#max(min(maxn, n), minn)

        
        #update start time
        
        for seq in range(num_packets):
            self.OpELD_start_time[datapath.id][out_port][seq]=time.time()
            SEQ=(seq).to_bytes(SEQ_size, byteorder="big")
             
            opeld_packet=opeld_header+SEQ+bytearray(extra_byte)
            out = parser.OFPPacketOut(datapath=datapath, buffer_id=ofp.OFP_NO_BUFFER,
                                  match=match, actions=actions, data=opeld_packet)
            datapath.send_msg(out)
         
        for k in self.OpELD_start_time[datapath.id][out_port].keys():
            if k>=num_packets:
                del self.OpELD_start_time[datapath.id][out_port][k]
            
         
        
# ────────────────────────────────────────────────────────────────────────────────
    # NOTE send_arp_packet
    def send_arp_packet(self, datapath, in_port, out_port, opcode, src_mac, src_ip, dst_mac, dst_ip):
        """opcode:1 request"""
        """opcode:2 reply"""
        ofp = datapath.ofproto
        parser = datapath.ofproto_parser
        pkt = packet.Packet()
        pkt.add_protocol(ethernet.ethernet(
            ethertype=ether_types.ETH_TYPE_ARP, dst=dst_mac, src=src_mac))
        pkt.add_protocol(arp.arp(opcode=opcode, src_mac=src_mac,
                                 src_ip=src_ip, dst_mac=dst_mac, dst_ip=dst_ip))
        pkt.serialize()
        data = pkt.data
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

        """
        self.logger.debug('OFPFlowRemoved received: '
                        'cookie=%d priority=%d reason=%s table_id=%d '
                        'duration_sec=%d duration_nsec=%d '
                        'idle_timeout=%d hard_timeout=%d '
                        'packet_count=%d byte_count=%d match.fields=%s',
                        msg.cookie, msg.priority, reason, msg.table_id,
                        msg.duration_sec, msg.duration_nsec,
                        msg.idle_timeout, msg.hard_timeout,
                        msg.packet_count, msg.byte_count, msg.match)
    """
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
 
        self.G.nodes[datapath.id]["port"][msg.desc.port_no]["OFPMP_PORT_DESC"] = data

        if msg.reason == ofp.OFPPR_ADD:
            """ADD"""
            pass

        elif msg.reason == ofp.OFPPR_DELETE:
            """DELETE"""

            # doing storage all_port_duration_s_temp
            try:
                self.G.nodes[datapath.id]["all_port_duration_s_temp"] = int(self.G.nodes[datapath.id]["all_port_duration_s_temp"])+int(
                    self.G.nodes[datapath.id]["port"][msg.desc.port_no]["OFPMP_PORT_STATS"]["duration_sec"])
            except:
                self.G.nodes[datapath.id]["all_port_duration_s_temp"] = 0

            # NOTE difference with OF1.5
            # Implementation add this to port state "0",define the port have been ""DELETE"" by OVSDB
            # data["state"]
            # Openflow Extend Port State= 0 ,sort name:OPEPS /*the port have been ""DELETE"" */
            # OFPPS_LINK_DOWN = 1, /* No physical link present. */
            # OFPPS_BLOCKED = 2, /* Port is blocked */
            # OFPPS_LIVE = 4, /* Live for Fast Failover Group. */
            data["state"] = self.OpEPS
            self.G.nodes[datapath.id]["port"][msg.desc.port_no]["OFPMP_PORT_DESC"] = data
 
        elif msg.reason == ofp.OFPPR_MODIFY:
            """MODIFY"""
            if ofp_port_state == ofp.OFPPS_LINK_DOWN:
                """OFPPS_LINK_DOWN"""
                pass
            elif ofp_port_state == ofp.OFPPS_BLOCKED:
                """OFPPS_BLOCKED"""
                pass
                #del self.G.nodes[datapath.id]["port"][msg.desc.port_no]
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

    #NOTE: _packet_in_handler
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
                 
                seq=int.from_bytes(msg.data[14:16], "big")
                self.handle_opeld(datapath, port, pkt_ethernet,seq)

        else:
            # TODO LOG ERROR
            return

        pkt_icmp = pkt.get_protocol(icmp.icmp)
        if pkt_icmp:
            pass

        pkt_arp = pkt.get_protocol(arp.arp)
        if pkt_arp:
            self.handle_arp(datapath, pkt_arp, port)

        pkt_lldp = pkt.get_protocol(lldp.lldp)
        if pkt_lldp:
            self.handle_lldp(datapath, port, pkt_ethernet, pkt_lldp)

    def handle_arp(self, datapath, pkt_arp, in_port):
        ofp = datapath.ofproto
        # https://www.iana.org/assignments/arp-parameters/arp-parameters.xhtml
        # REQUEST = 1
        # REPLY   = 2
        ARP_request = 1
        ARP_reply = 2
        if in_port < ofp.OFPP_MAX:
            if pkt_arp.opcode == ARP_request:
                if pkt_arp.src_ip not in self.ARP_Table:
                    self.G.nodes[datapath.id]["port"][in_port]["host"][pkt_arp.src_ip] = pkt_arp.src_mac
                    self.ARP_Table[pkt_arp.src_ip] = pkt_arp.src_mac

                if pkt_arp.dst_ip in self.ARP_Table:
                    self.send_arp_packet(datapath=datapath, in_port=ofp.OFPP_CONTROLLER, out_port=in_port, opcode=ARP_reply,
                                         src_mac=self.ARP_Table[pkt_arp.dst_ip], src_ip=pkt_arp.dst_ip, dst_mac=pkt_arp.src_mac, dst_ip=pkt_arp.src_ip)
            else:
                # TODO HADLE EXPECTION
                pass

        # Openflow Extend Link Detect(OpELD) Topology/Link Detect
    
    # SECTION handle_opeld
    def handle_opeld(self, datapath, port, pkt_opeld,seq):
        # NOTE Topology maintain
        def init_edge(start_switch, end_switch):
            self.G.add_edge(start_switch, end_switch)
            self.G[start_switch][end_switch]["port"] = nested_dict()
            self.G[start_switch][end_switch]["port"][start_switch] = []
            self.G[start_switch][end_switch]["port"][end_switch] = []
            self.G[start_switch][end_switch]["tmp"] = nested_dict()
            self.G[start_switch][end_switch]["detect"] = nested_dict()

        def add_edge_port_pair(start_switch, start_port, end_switch, end_port):

            if start_port not in self.G[start_switch][end_switch]["port"][start_switch]:
                self.G[start_switch][end_switch]["port"][start_switch].append(
                    start_port)

            if end_port not in self.G[start_switch][end_switch]["port"][end_switch]:
                self.G[start_switch][end_switch]["port"][end_switch].append(
                    end_port)

        start_switch, start_port = self.decode_opeld(
            pkt_opeld.dst, pkt_opeld.src)
        end_switch = datapath.id
        end_port = port

        #NOTE Topology setting
        if not self.G.has_edge(start_switch, end_switch):
            init_edge(start_switch, end_switch)
        
        add_edge_port_pair(start_switch, start_port, end_switch, end_port)
           

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
                start_time=self.OpELD_start_time[start_switch][start_port][seq]
            
                end_time=time.time()
                link_index=self.G[start_switch][end_switch]["port"][start_switch].index(start_port)
                start_switch_latency=self.echo_latency[start_switch]
                end_switch_latency=self.echo_latency[end_switch]
                #negative beacuse start_switch_latency+end_switch_latency>(time.time()-start_time)
                
                
                self.G[start_switch][end_switch]["tmp"][link_index][seq]["start"]=start_time+start_switch_latency
                self.G[start_switch][end_switch]["tmp"][link_index][seq]["end"]=end_time-end_switch_latency
        except:
            #FIXME :!!!!
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

    #NOTE route
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
        #print('OFPEchoRequest received: data=%s',(ev.msg.data))

    def send_echo_reply(self, datapath, data):
        ofp_parser = datapath.ofproto_parser

        reply = ofp_parser.OFPEchoReply(datapath, data)
        datapath.send_msg(reply)

    @set_ev_cls(ofp_event.EventOFPEchoReply, [HANDSHAKE_DISPATCHER, CONFIG_DISPATCHER, MAIN_DISPATCHER])
    def _echo_reply_handler(self, ev):
        #print('OFPEchoRequest received2: data=%s',(ev.msg.data))
        # self.echo_latency[]
        now_timestamp = time.time()
        try:
            latency = now_timestamp - float(ev.msg.data)#Round-trip delay time
            self.echo_latency[ev.msg.datapath.id] = latency/2#End-to-end delay
        except:
            return

        #print('EventOFPEchoReply received: data=%s',(latency*1000))

    # !SECTION
    # NOTE EventOFPErrorMsg

    @set_ev_cls(ofp_event.EventOFPErrorMsg, [HANDSHAKE_DISPATCHER, CONFIG_DISPATCHER, MAIN_DISPATCHER])
    def error_msg_handler(self, ev):
        msg = ev.msg

        print('OFPErrorMsg received: type=0x%02x code=0x%02x message=%s',
              msg.type, msg.code, (msg.data))

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
