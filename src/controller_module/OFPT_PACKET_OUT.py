
from ryu.lib.packet import ethernet, arp
from ryu.lib.packet import ether_types
from ryu.ofproto import ofproto_v1_5
from ryu.lib.packet import packet
from ryu.lib import hub
from controller_module import GLOBAL_VALUE

def arp_request_all(dst_ip):
    "暴力搜尋dst_ip的mac為多少:目的維護arp與了解到底哪個ip在哪個port這樣才能路由"
    for node_id in GLOBAL_VALUE.G.copy().nodes:
        if GLOBAL_VALUE.check_node_is_switch(node_id):
            switch_data = GLOBAL_VALUE.G.nodes[node_id]
            for port_no in switch_data["port"].keys():
                # if the port can working
                if switch_data["port"][port_no]["OFPMP_PORT_DESC"]["state"] == ofproto_v1_5.OFPPS_LIVE:
                    # arp_src_ip="0.0.0.0"這種是ARP probe型態的封包
                    # An ARP Probe with an all-zero 'sender IP address' -rfc5227 [Page 6]
                    hub.spawn(send_arp_packet, datapath=switch_data["datapath"], out_port=port_no, eth_src_mac='00:00:00:00:00:00', eth_dst_mac="ff:ff:ff:ff:ff:ff", arp_opcode=arp.ARP_REQUEST,
                                arp_src_mac='00:00:00:00:00:00', arp_src_ip="0.0.0.0", arp_dst_mac='00:00:00:00:00:00', arp_dst_ip=dst_ip, payload=GLOBAL_VALUE.ARP_SEND_FROM_CONTROLLER)

def send_arp_packet(datapath, out_port, eth_src_mac, eth_dst_mac, arp_opcode, arp_src_mac, arp_src_ip, arp_dst_mac, arp_dst_ip, payload):
    """opcode:1 request"""
    """opcode:2 reply"""
    ofp = datapath.ofproto
    in_port = ofp.OFPP_CONTROLLER
    parser = datapath.ofproto_parser
    pkt = packet.Packet()
    pkt.add_protocol(ethernet.ethernet(
        ethertype=ether_types.ETH_TYPE_ARP, src=eth_src_mac, dst=eth_dst_mac))
    pkt.add_protocol(arp.arp(opcode=arp_opcode, src_mac=arp_src_mac,
                                src_ip=arp_src_ip, dst_mac=arp_dst_mac, dst_ip=arp_dst_ip))
    pkt.serialize()
    data = pkt.data+payload
    match = datapath.ofproto_parser.OFPMatch(in_port=in_port)
    actions = [parser.OFPActionOutput(port=out_port)]

    out = parser.OFPPacketOut(datapath=datapath, buffer_id=ofp.OFP_NO_BUFFER,
                                match=match, actions=actions, data=data)
    datapath.send_msg(out)