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
CONF = cfg.CONF


class MonitorModule(app_manager.RyuApp):
    """
    負責更新統計網路狀態
    """
    OFP_VERSIONS = [ofproto_v1_5.OFP_VERSION]
    def __init__(self, *args, **kwargs):
        super(MonitorModule, self).__init__(*args, **kwargs)    
        self.G=2


    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
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
                # 這個是在傳送openflow協定的時候標示的xid,當發生錯誤的時候交換機會回傳同個xid,讓我們知道剛剛哪個傳送的openflow發生錯誤
                self.G.nodes[node_id]["now_max_xid"] = 0
                self.G.nodes[(datapath.id,None)]["GROUP_TABLE"]=nested_dict()

            # set_meter_table is in _port_desc_stats_reply_handler
            # FIXME EDGE SWITCH AND TRANSIT SWITCH flow table 1 NOT ADD YET
        def set_flow_table_0_control_and_except():
            # Control and exception handling packets
            # set_flow_table_0_DSCP() is in _port_desc_stats_reply_handler
            self.control_and_except(datapath, eth_type=self.OpELD_EtherType)
            self.control_and_except(datapath, eth_type=self.OpEQW_EtherType)
            self.control_and_except(
                datapath, eth_type=ether_types.ETH_TYPE_ARP)
            self.control_and_except(datapath, eth_type=ether_types.ETH_TYPE_IPV6,
                                    ip_proto=in_proto.IPPROTO_ICMPV6, icmpv6_type=icmpv6.ND_NEIGHBOR_SOLICIT)
            self.add_all_flow_to_table(datapath, 0, 1)

        def set_flow_table_1():
            self.add_all_flow_to_table(datapath, 1, 2)

        def set_flow_table_2():
            # FIXME 關於未知封包,可以嘗試實做buffer  max_len 或是buffer_id能加速? 請參考opnflow1.51-7.2.6.1 Output Action Structures
            self.unknow_route_ask_controller(datapath)
        msg = ev.msg
        datapath = msg.datapath
        self.send_port_desc_stats_request(datapath)
        init_node()

        set_flow_table_0_control_and_except()
        set_flow_table_1()
        set_flow_table_2()