import ryu
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
import time
from nested_dict import *
import numpy as np

from controller_module.utils import log, dict_tool
from controller_module import GLOBAL_VALUE
from controller_module import OFPT_FLOW_MOD,OFPT_PACKET_OUT
from controller_module.route_metrics import formula
from controller_module.OFPT_PACKET_OUT import send_arp_packet 
CONF = cfg.CONF


class MonitorModule(app_manager.RyuApp):
    OpELD_start_time = nested_dict()
    echo_latency = {}
    monitor_thread = None 
    delta = 3  # sec,using in _monitor() ,to control update speed
    monitor_link_wait = 1
    monitor_sent_opedl_packets = 50
    "一次發送多少個封包"
    monitor_each_opeld_extra_byte = 0  # self.MTU-16#max=
    "每個封包額外大小 最大數值為::py:attr:`~controller_module.GLOBAL_VALUE.MTU`-16(OPELD header size)"
    monitor_wait_opeld_back = 2  # sec 超過此時間的封包都會被當作遺失
    "超過此時間的封包都會被monitor當作遺失"
    monitor_wait_update_path=10
    ARP_Table = {}  # for more hight speed
    "維護arp table"
     

    """
    負責更新統計網路狀態::py:attr:`~controller_module.GLOBAL_VALUE.G`
    拓樸GLOBAL_VALUE.G的結構:
        ::

                    weight=0         Edge          weight=0
                     +----+        +-------+        +----+
             Switch1 v    | port22 v       | port55 v    |Switch2
            +--------+    +--------+       +--------+    +--------+
            |(1,None)|    | (1,22) |       | (2,55) |    |(2,None)|
            +--------+    +--------+       +--------+    +--------+
              Node   |    ^        |       ^        |    ^  Node
                     +----+        +-------+        +----+
                    weight=0         Edge          weight=0
        ::

    """
    OFP_VERSIONS = [ofproto_v1_5.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(MonitorModule, self).__init__(*args, **kwargs)
        self.monitor_thread = hub.spawn(self.monitor)
         
    def init_node(self, datapath):
        """
        初始化交換機節點在拓樸
        """
        node_id = (datapath.id, None)
        if not GLOBAL_VALUE.G.has_node(node_id):
            GLOBAL_VALUE.G.add_node(node_id)
            GLOBAL_VALUE.G.nodes[node_id]["datapath"] = datapath
            GLOBAL_VALUE.G.nodes[node_id]["port"] = nested_dict()
            GLOBAL_VALUE.G.nodes[node_id]["all_port_duration_s_temp"] = 0
            GLOBAL_VALUE.G.nodes[node_id]["all_port_duration_s"] = 0
            GLOBAL_VALUE.G.nodes[node_id]["FLOW_TABLE"] = nested_dict()
            GLOBAL_VALUE.G.nodes[node_id]["now_max_group_id"] = 0
            # 這個是在傳送openflow協定的時候標示的xid,當發生錯誤的時候交換機會回傳同個xid,讓我們知道剛剛哪個傳送的openflow發生錯誤
            GLOBAL_VALUE.G.nodes[node_id]["now_max_xid"] = 0
            GLOBAL_VALUE.G.nodes[(datapath.id, None)
                                 ]["GROUP_TABLE"] = nested_dict()

    def init_port_node(self, datapath, port_no):
        """
        初始化交換機的port節點在拓樸
        """
        switch_id = (datapath.id, None)
        port_id = (datapath.id, port_no)
        if not GLOBAL_VALUE.G.has_node(port_id):
            GLOBAL_VALUE.G.add_node(port_id)
        if not GLOBAL_VALUE.G.has_edge(switch_id, port_id):
            GLOBAL_VALUE.G.add_edge(switch_id, port_id, weight=0)
        if not GLOBAL_VALUE.G.has_edge(port_id, switch_id):
            GLOBAL_VALUE.G.add_edge(port_id, switch_id, weight=0)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        """
        當交換機連線完成
        OFPT_FEATURES_REPLY
        """
        # set_meter_table is in _port_desc_stats_reply_handler
        # FIXME EDGE SWITCH AND TRANSIT SWITCH flow table 1 NOT ADD YET
        msg = ev.msg
        datapath = msg.datapath
        self.send_port_desc_stats_request(datapath)
        self.init_node(datapath)

        self.set_flow_table_0_control_and_except(datapath)
        self.set_flow_table_1(datapath)
        self.set_flow_table_2(datapath)

    def set_flow_table_0_control_and_except(self, datapath: ryu.controller.controller.Datapath):
        "負責在交換機flow table 0 過濾需要特殊處理的封包給控制器"
        # Control and exception handling packets
        # set_flow_table_0_DSCP() is in _port_desc_stats_reply_handler
        self.control_and_except(
            datapath, eth_type=GLOBAL_VALUE.OpELD_EtherType)
        self.control_and_except(
            datapath, eth_type=GLOBAL_VALUE.OpEQW_EtherType)
        self.control_and_except(
            datapath, eth_type=ether_types.ETH_TYPE_ARP)
        self.control_and_except(datapath, eth_type=ether_types.ETH_TYPE_IPV6,
                                ip_proto=in_proto.IPPROTO_ICMPV6, icmpv6_type=icmpv6.ND_NEIGHBOR_SOLICIT)
        self.add_all_flow_to_table(datapath, 0, 1)

    def set_flow_table_1(self, datapath):
        "設定flow table 1 的flow entry"
        self.add_all_flow_to_table(datapath, 1, 2)
    def table_1_change_update_package(self, datapath,in_port):
        ofp = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch(in_port=in_port)
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER)]
        # 封包從table 1 複製 到 控制器 與table2
        inst = [parser.OFPInstructionActions(
            ofp.OFPIT_APPLY_ACTIONS, actions), parser.OFPInstructionGotoTable(2)]
        mod = parser.OFPFlowMod(datapath=datapath, table_id=1, priority=1,
                                command=ofp.OFPFC_ADD, match=match, instructions=inst)
        OFPT_FLOW_MOD.send_ADD_FlowMod(mod)
        
    def set_flow_table_2(self, datapath):
        # FIXME 關於未知封包,可以嘗試實做buffer  max_len 或是buffer_id能加速? 請參考opnflow1.51-7.2.6.1 Output Action Structures
        "設定flow table 2 的flow entry"
        self.unknow_route_ask_controller(datapath)

    def control_and_except(self, datapath, **kwargs):
        "設定flow table 0 過濾要特殊處理的封包"
        ofp = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch(**kwargs)
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER)]
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=65535, table_id=0,
                                command=ofp.OFPFC_ADD, match=match, instructions=inst, hard_timeout=0)
        OFPT_FLOW_MOD.send_ADD_FlowMod(mod)

    def add_all_flow_to_table(self, datapath, from_table_id, to_table_id):
        "所有封包從`from_table_id`轉送到`to_table_id`"
        ofp = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        inst = [parser.OFPInstructionGotoTable(to_table_id)]
        mod = parser.OFPFlowMod(datapath=datapath, table_id=from_table_id, priority=0,
                                command=ofp.OFPFC_ADD, match=match, instructions=inst)
        OFPT_FLOW_MOD.send_ADD_FlowMod(mod)

    def unknow_route_ask_controller(self, datapath):
        "flow table 2負責路由,當交換機未知此封包如何路由需要轉送給交換機"
        ofp = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER)]
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=0, table_id=2,
                                command=ofp.OFPFC_ADD, match=match, instructions=inst, hard_timeout=0)
        OFPT_FLOW_MOD.send_ADD_FlowMod(mod)


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
    def port_stats_reply_handler(self, ev):
        """
        port 的統計狀態     
        """
        msg = ev.msg
        datapath = msg.datapath
        ofp = datapath.ofproto
        all_port_duration_s_temp = GLOBAL_VALUE.G.nodes[(
            datapath.id, None)]["all_port_duration_s_temp"]
        # get the list of "close port"
        close_port = list(GLOBAL_VALUE.G.nodes[(datapath.id, None)]["port"].keys())
        all_port_duration_s = 0
        for OFPPortStats in ev.msg.body:
            if OFPPortStats.port_no < ofp.OFPP_MAX:
                # OFPPortStats is a "class",so it need to covent to dict

                data = dict_tool.class2dict(OFPPortStats)

                data["update_time"] = time.time()

                # for short cut
                OFPMP_PORT_STATS = GLOBAL_VALUE.G.nodes[(
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
                GLOBAL_VALUE.G.nodes[(
                    datapath.id, None)]["port"][OFPPortStats.port_no]["OFPMP_PORT_STATS"] = data
                # count all_port_duration_s
                all_port_duration_s = all_port_duration_s_temp + \
                    data["duration_sec"]

                close_port.remove(OFPPortStats.port_no)
        GLOBAL_VALUE.G.nodes[(datapath.id, None)
                     ]["all_port_duration_s"] = all_port_duration_s

        # clear close port delta
        for close in close_port:
            GLOBAL_VALUE.G.nodes[(datapath.id, None)
                         ]["port"][close]["OFPMP_PORT_STATS"]["rx_bytes_delta"] = 0
            GLOBAL_VALUE.G.nodes[(datapath.id, None)
                         ]["port"][close]["OFPMP_PORT_STATS"]["tx_bytes_delta"] = 0
            pass



    def send_port_desc_stats_request(self, datapath):
        "跟交換機要port的規格資訊"
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser
        req = ofp_parser.OFPPortDescStatsRequest(datapath, 0, ofp.OFPP_ANY)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPPortDescStatsReply, MAIN_DISPATCHER)
    def port_desc_stats_reply_handler(self, ev):
        """reply OFPMP_PORT_DESCRIPTION,接收port的規格細節請看-openflow spec 1.5.1-7.2.1.1 Port Description Structures

        ::

                     weight=0
                     +----+
            交換機    |    | port
            +--------+    +--------+
            |(1,None)|    | (1,22) |
            +--------+    +--------+
                     |      |   
                     +------+
                     weight=0
        ::
        """
        msg = ev.msg
        datapath = msg.datapath
        ofp = datapath.ofproto
        for OFPPort in ev.msg.body:
            if OFPPort.port_no < ofp.OFPP_MAX:

                """{"port_no": 1, "length": 72, "hw_addr": "be:f3:b6:8a:f8:1e", "config": 0,"state": 4, "properties": [{"type": 0, "length": 32, "curr": 2112,"advertised": 0, "supported": 0, "peer": 0, "curr_speed": 10000000,"max_speed": 0}], "update_time": 1552314248.2066813
                }"""
                data = dict_tool.class2dict(OFPPort)
                data["update_time"] = time.time()

                GLOBAL_VALUE.G.nodes[(datapath.id, None)
                                     ]["port"][OFPPort.port_no]["OFPMP_PORT_DESC"] = data
                self.init_port_node(datapath, OFPPort.port_no)

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
        """
        # NOTE Openflow Extend Link Detect(OpELD)
        # uint64_t datapath_id OF1.5 SPEC
        # uint32_t port_no OF1.5 SPEC
        # uint16_t eth_type=0X1105,or GLOBAL_VALUE.OpELD_EtherType
        # uint16_t: Sequence Number(SEQ)
        ::

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
        ::
        """
        opeld_header_size = 14  # bytes
        SEQ_size = 2  # bytes
        min_opeld_size = opeld_header_size+SEQ_size
        ofp = datapath.ofproto
        parser = datapath.ofproto_parser
        pkt = packet.Packet()
        dst, src = self.encode_opeld(datapath.id, out_port)
        pkt.add_protocol(ethernet.ethernet(
            ethertype=GLOBAL_VALUE.OpELD_EtherType, dst=dst, src=src))
        pkt.serialize()
        # default MTU Max is 1500
        if not 0 <= extra_byte <= GLOBAL_VALUE.MTU-min_opeld_size:
            #log.Global_Log[log_file_name].warning('extra_byte out of size')
            # max(min(maxn, n), minn)
            extra_byte = max(min(GLOBAL_VALUE.MTU-min_opeld_size, extra_byte), 0)

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
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        """
        非同步接收來自交換機OFPT_PACKET_IN message
        """
        msg = ev.msg
        datapath = msg.datapath
        port = msg.match['in_port']
        pkt = packet.Packet(data=msg.data)
        pkt_ethernet = pkt.get_protocol(ethernet.ethernet)
        if pkt_ethernet:
            if pkt_ethernet.ethertype == GLOBAL_VALUE.OpELD_EtherType:
                # print("get",self.decode_eth_1105(pkt_ethernet.dst,pkt_ethernet.src))
                seq = int.from_bytes(msg.data[14:16], "big")
                self.handle_opeld(datapath, port, pkt_ethernet, seq)
        else:
            # TODO LOG ERROR
            return
        pkt_arp = pkt.get_protocol(arp.arp)
        if pkt_arp:
            # print("問")
            self.handle_arp(datapath, pkt_arp, port, msg.data)
    def handle_opeld(self, datapath, port, pkt_opeld, seq):
        # NOTE Topology maintain
        def init_edge(start_node_id, end_node_id):
            print("拓樸", start_node_id, end_node_id)
            GLOBAL_VALUE.G.add_edge(start_node_id, end_node_id)
            GLOBAL_VALUE.G[start_node_id][end_node_id]["tmp"] = nested_dict()
            GLOBAL_VALUE.G[start_node_id][end_node_id]["detect"] = nested_dict()

        start_switch, start_port = self.decode_opeld(
            pkt_opeld.dst, pkt_opeld.src)
        end_switch = datapath.id
        end_port = port
        start_node_id = (start_switch, start_port)
        end_node_id = (end_switch, end_port)
        # NOTE Topology setting
        if not GLOBAL_VALUE.G.has_edge(start_node_id, end_node_id):
            init_edge(start_node_id, end_node_id)
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

                GLOBAL_VALUE.G[start_node_id][end_node_id]["tmp"][seq]["start"] = start_time + \
                    start_switch_latency
                GLOBAL_VALUE.G[start_node_id][end_node_id]["tmp"][seq]["end"] = end_time - \
                    end_switch_latency
        except:
            # FIXME :!!!!
            pass
    def handle_arp(self, datapath, pkt_arp, in_port, packet):
        def update_fome_arp_data(datapath, pkt_arp, in_port):
            # FIXME
            self.table_1_change_update_package(datapath,in_port)
            GLOBAL_VALUE.G.nodes[(
                datapath.id, None)]["port"][in_port]["host"][pkt_arp.src_ip] = pkt_arp.src_mac
            self.ARP_Table[pkt_arp.src_ip] = pkt_arp.src_mac
            GLOBAL_VALUE.ip_get_datapathid_port[pkt_arp.src_ip]["datapath_id"] = datapath.id
            GLOBAL_VALUE.ip_get_datapathid_port[pkt_arp.src_ip]["port"] = in_port
 

        # 避免廣播風暴會拒絕最後2個bytes==ARP_SEND_FROM_CONTROLLER
        last_two_bytes = packet[-2:]
        # reject and do not process the arp packet ask from controller
        if last_two_bytes == GLOBAL_VALUE.ARP_SEND_FROM_CONTROLLER:
            return
        ofp = datapath.ofproto
        if in_port < ofp.OFPP_MAX:
            if pkt_arp.opcode == arp.ARP_REQUEST:
                update_fome_arp_data(datapath, pkt_arp, in_port)
                if pkt_arp.dst_ip in self.ARP_Table:
                    hub.spawn(send_arp_packet, datapath=datapath, out_port=in_port, eth_src_mac=self.ARP_Table[pkt_arp.dst_ip], eth_dst_mac=pkt_arp.src_mac, arp_opcode=arp.ARP_REPLY,
                              arp_src_mac=self.ARP_Table[pkt_arp.dst_ip], arp_src_ip=pkt_arp.dst_ip, arp_dst_mac=pkt_arp.src_mac, arp_dst_ip=pkt_arp.src_ip, payload=GLOBAL_VALUE.ARP_SEND_FROM_CONTROLLER)
                else:
                    # TODO : send to all switch all port to check!
                    OFPT_PACKET_OUT.arp_request_all(pkt_arp.dst_ip)
                    pass
            elif pkt_arp.opcode == arp.ARP_REPLY:
                
                update_fome_arp_data(datapath, pkt_arp, in_port)

            else:
                # TODO HADLE EXPECTION
                pass
    def send_echo_request(self, datapath):
        "控制器問交換機"
        ofp_parser = datapath.ofproto_parser
        echo_req = ofp_parser.OFPEchoRequest(datapath,
                                             data=b"%.12f" % time.time())
        datapath.send_msg(echo_req)

    @set_ev_cls(ofp_event.EventOFPEchoReply, [HANDSHAKE_DISPATCHER, CONFIG_DISPATCHER, MAIN_DISPATCHER])
    def echo_reply_handler(self, ev):
        "交換機回答控制器"
        now_timestamp = time.time()
        try:
            # Round-trip delay time
            latency = now_timestamp - float(ev.msg.data)
            self.echo_latency[ev.msg.datapath.id] = latency / 2  # End-to-end delay
        except:
            return
    


    def monitor(self):
        hub.sleep(3)
        # 更新路徑統計
        def _update_path():
            while True:
                hub.sleep(self.monitor_wait_update_path)
                for dst, v in list(GLOBAL_VALUE.PATH.items()):
                    for priority, dst_priority_path in list(v.items()):
                        if "package" not in dst_priority_path:
                            continue
                        latency = []
                        all_timestamp = []
                        for package, delay in list(dst_priority_path["package"]["start"].items()):
                            _start_time = delay
                            if dst_priority_path["package"]["end"][package] == {}:
                                continue
                            _end_time = dst_priority_path["package"]["end"][package]
                            all_timestamp.append(_end_time)
                            all_timestamp.append(_start_time)
                            _delay = (_end_time-_start_time)  # s
                            latency.append(_delay)
                        if all_timestamp==[]:
                            continue   
                        delay_one_packet = abs(np.mean(latency)*1000)  # ms
                        jitter = abs(np.std(latency) * 1000)
                        all_bytes = 0
                        for _package, delay in list(dst_priority_path["package"]["end"].items()):
                            all_bytes = all_bytes+len(_package)
                        bandwidth_bytes_per_s = all_bytes / \
                            (max(all_timestamp)-min(all_timestamp))
                        loss_percent = (len(dst_priority_path["package"]["start"])-len(
                            dst_priority_path["package"]["end"]))/len(dst_priority_path["package"]["start"])
                        GLOBAL_VALUE.PATH[dst][priority]["detect"]["latency_ms"] = delay_one_packet
                        GLOBAL_VALUE.PATH[dst][priority]["detect"]["jitter_ms"] = jitter
                        GLOBAL_VALUE.PATH[dst][priority]["detect"]["loss_percent"] = loss_percent
                        GLOBAL_VALUE.PATH[dst][priority]["detect"]["bandwidth_bytes_per_s"] = bandwidth_bytes_per_s
                for src, v in list(GLOBAL_VALUE.PATH.items()):
                    for dst, dst_priority_path in list(v.items()):
                        if "package" in GLOBAL_VALUE.PATH[dst][priority]:
                            del GLOBAL_VALUE.PATH[dst][priority]["package"]
        def decorator_node_iteration(func):
            def node_iteration():
                while True:
                    for node_id in GLOBAL_VALUE.G.copy().nodes:
                        if GLOBAL_VALUE.check_node_is_switch(node_id):
                            datapath = GLOBAL_VALUE.G.nodes[node_id]["datapath"]
                            func(datapath)
                    hub.sleep(self.delta)
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
                for edge in list(GLOBAL_VALUE.G.edges()):
                    edge_id1 = edge[0]
                    edge_id2 = edge[1]
                    if GLOBAL_VALUE.check_edge_is_link(edge_id1, edge_id2):
                        # GLOBAL_VALUE.G[start_switch][end_switch]["port"][end_switch]
                        link_data = GLOBAL_VALUE.G[edge_id1][edge_id2]
                        link_data["tmp"] = nested_dict()

            def sent_opeld_to_all_port():
                for node_id in GLOBAL_VALUE.G.copy().nodes:
                    if GLOBAL_VALUE.check_node_is_switch(node_id):
                        switch_data = GLOBAL_VALUE.G.nodes[node_id]
                        #
                        switch_data = switch_data.copy()
                        for port_no in switch_data["port"].keys():
                            # if the port can working
                            if switch_data["port"][port_no]["OFPMP_PORT_DESC"]["state"] == ofproto_v1_5.OFPPS_LIVE:
                                hub.spawn(self.send_opeld_packet,
                                        switch_data["datapath"], port_no, extra_byte=self.monitor_each_opeld_extra_byte, num_packets=self.monitor_sent_opedl_packets)
            while True:

                # 統計鏈路
                # NOTE start
                # print(GLOBAL_VALUE.G.nodes[datapath.id]["port"][1]["OFPMP_PORT_DESC"]["properties"],datapath.id)
                clear_link_tmp_data()  # 重算所有統計
                # sent opeld to all port of each switch for doing link detect and topology detect
                sent_opeld_to_all_port()  # 發送封包
                # wait for packet back
                hub.sleep(self.monitor_wait_opeld_back)
                # print(GLOBAL_VALUE.G[2][1]["tmp"])
                # print(GLOBAL_VALUE.G[2][1]["port"])
                for edge in list(GLOBAL_VALUE.G.edges()):
                    edge_id1 = edge[0]
                    edge_id2 = edge[1]
                    if GLOBAL_VALUE.check_edge_is_link(edge_id1, edge_id2):
                        start_switch = (edge_id1[0], None)
                        start_port_number = edge_id1[1]
                        end_switch = (edge_id2[0], None)
                        end_port_number = edge_id2[1]
                        # print(GLOBAL_VALUE.G[start_switch][end_switch]["tmp"])
                        packet_start_time = []
                        packet_end_time = []
                        seq_packet = GLOBAL_VALUE.G[edge_id1][edge_id2]["tmp"]
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

                        if len(packet_end_time) != 0 or len(packet_start_time) != 0:

                            curr_speed = min(int(GLOBAL_VALUE.G.nodes[start_switch]["port"][start_port_number]["OFPMP_PORT_DESC"]["properties"][0]["curr_speed"]), int(
                                GLOBAL_VALUE.G.nodes[end_switch]["port"][end_port_number]["OFPMP_PORT_DESC"]["properties"][0]["curr_speed"]))  # curr_speed kbps

                            tx_bytes_delta = int(
                                GLOBAL_VALUE.G.nodes[start_switch]["port"][start_port_number]["OFPMP_PORT_STATS"]["tx_bytes_delta"])

                            jitter = abs(np.std(latency) * 1000)  # millisecond
                            # A. S. Tanenbaum and D. J. Wetherall, Computer Networks, 5th ed. Upper Saddle River, NJ, USA: Prentice Hall Press, 2010.
                            # "The variation (i.e., standard deviation) in the delay or packet arrival times is called jitter."
                            # default one packet from A TO B latency millisecond(ms)
                            delay_one_packet = abs(np.mean(latency)*1000)
                            loss = 1-(get_packets_number /
                                    self.monitor_sent_opedl_packets)
                            # bytes_s=(get_packets_number*(self.monitor_each_opeld_extra_byte+16))/all_t

                            # available using bandwith bytes per second
                            # curr_speed is kbps
                            bw = ((1000*curr_speed)/8) - \
                                (tx_bytes_delta/self.delta)
                            # print(start_switch,end_switch,link_index,"jitter",jitter,"delay_one_packet",delay_one_packet,"loss",loss,"gbytes_s",bw)

                            # millisecond
                            GLOBAL_VALUE.G[edge_id1][edge_id2]["detect"]["jitter_ms"] = jitter
                            # %how many percent of the packet loss
                            GLOBAL_VALUE.G[edge_id1][edge_id2]["detect"]["loss_percent"] = loss
                            # available bandwidth
                            GLOBAL_VALUE.G[edge_id1][edge_id2]["detect"]["bandwidth_bytes_per_s"] = bw
                            # from a to b ,just one way ,millisecond
                            GLOBAL_VALUE.G[edge_id1][edge_id2]["detect"]["latency_ms"] = delay_one_packet

                            # 這裡你可以自創演算法去評估權重
                            GLOBAL_VALUE.G[edge_id1][edge_id2]["weight"] = formula.OSPF(
                                bw*8)
                            GLOBAL_VALUE.G[edge_id1][edge_id2]["hop"] = 1
                            GLOBAL_VALUE.G[edge_id1][edge_id2]["low_delay"] = delay_one_packet
                            GLOBAL_VALUE.G[edge_id1][edge_id2]["low_jitter"] = jitter


                            GLOBAL_VALUE.G[edge_id1][edge_id2]["EIGRP"] = formula.EIGRP(
                                (bw*8)/1000, curr_speed, tx_bytes_delta, delay_one_packet, loss)
                            # FIXME 新增演算法 路線 取最小的頻寬 當最佳

                            # print(nx.shortest_path(GLOBAL_VALUE.G,(1,None),(2,None),weight="weight"),nx.shortest_path_length(GLOBAL_VALUE.G,(1,None),(2,None),weight="weight"))
                            # try:
                            #print(list(islice(nx.shortest_simple_paths(GLOBAL_VALUE.G, (1,None), (2,None), weight="weight"), 2)))
                            # except:
                            #   pass
        # print("ok")
        self._sent_echo_thread = hub.spawn(_sent_echo)
        self._update_switch_thread = hub.spawn(_update_switch)
        self._update_link_thread = hub.spawn(_update_link)
        self._update_path_thread = hub.spawn(_update_path)
