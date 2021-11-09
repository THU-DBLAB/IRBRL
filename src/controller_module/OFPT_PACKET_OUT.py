from ryu.lib.packet import ether_types,ethernet, arp, icmp, ipv4,lldp
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
def Packout_to_FlowTable(tmp_datapath,data):
    print("Packout_to_FlowTable")
    ofp = tmp_datapath.ofproto
    parser = tmp_datapath.ofproto_parser
    match = tmp_datapath.ofproto_parser.OFPMatch(
        in_port=ofp.OFPP_CONTROLLER)
    actions = [parser.OFPActionOutput(port=ofp.OFPP_TABLE)]
    out = parser.OFPPacketOut(datapath=tmp_datapath, buffer_id=ofp.OFP_NO_BUFFER,
                                match=match, data=data,actions=actions)
   
    
    tmp_datapath.send_msg(out)
    
    print("Packout_to_FlowTable ok")


def send_icmp_packet( datapath, src="255.255.255", dst="255.255.255"):
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

def send_lldp_packet(datapath, port_no, data_size):
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
    
    datapath.send_msg(out)
    

   