#!/usr/bin/env python
# -*- coding: utf8 -*-
# 2016.07.31 kshuang

from ryu.base import app_manager
from ryu.ofproto import ofproto_v1_5
from ryu.controller.handler import set_ev_cls
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller import ofp_event
 
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
from ryu.lib.packet import lldp
from ryu.lib.packet import packet 
from ryu import utils
import time
class MyRyu(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_5.OFP_VERSION]
    normal_port = []
    lldp_topo = {}
    link_delay={}

    def __init__(self, *args, **kwargs):
        super(MyRyu, self).__init__(*args, **kwargs)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        print(msg)
        self.send_port_stats_request(datapath)


    def send_port_stats_request(self, datapath):
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser
        req = ofp_parser.OFPPortDescStatsRequest(datapath, 0, ofp.OFPP_ANY)
        datapath.send_msg(req)


    @set_ev_cls(ofp_event.EventOFPPortDescStatsReply, MAIN_DISPATCHER)
    def port_stats_reply_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # LLDP packet to controller
        match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_LLDP)
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER)]
        self.add_flow(datapath, 0, match, actions)
        
        for stat in ev.msg.body:
            if stat.port_no < ofproto.OFPP_MAX:
                self.send_lldp_packet(datapath, stat.port_no, stat.hw_addr)
                link_delay_element={"start":time.time(),"edn":None,"delay":None}
                self.link_delay[int(datapath.id),int(stat.port_no)]=link_delay_element
        #print("OFPP_MAX",ofproto.OFPP_MAX)
         
    def add_flow(self, datapath, priority, match, actions):
        ofp = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS,actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority, command=ofp.OFPFC_ADD, match=match, instructions=inst)
        datapath.send_msg(mod)


    def send_lldp_packet(self, datapath, port_no, hw_addr):
        ofp = datapath.ofproto
        pkt = packet.Packet()
        pkt.add_protocol(ethernet.ethernet(ethertype=ether_types.ETH_TYPE_LLDP,src=hw_addr ,dst=lldp.LLDP_MAC_NEAREST_BRIDGE))
        
        tlv_chassis_id = lldp.ChassisID(subtype=lldp.ChassisID.SUB_LOCALLY_ASSIGNED, chassis_id=str(datapath.id))
        tlv_port_id = lldp.PortID(subtype=lldp.PortID.SUB_LOCALLY_ASSIGNED, port_id=str(port_no))
        tlv_ttl = lldp.TTL(ttl=10)
        tlv_end = lldp.End()
        tlvs = (tlv_chassis_id, tlv_port_id, tlv_ttl, tlv_end)
        pkt.add_protocol(lldp.lldp(tlvs))
        pkt.serialize()

        data = pkt.data
        parser = datapath.ofproto_parser
        actions = [parser.OFPActionOutput(port=port_no)]
        match = datapath.ofproto_parser.OFPMatch(in_port=datapath.ofproto.OFPP_CONTROLLER)
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=ofp.OFP_NO_BUFFER, match=match, actions=actions, data=data)
        #print(time.time(),datapath.id,port_no)
        datapath.send_msg(out)


    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        #print(time.time())
        msg = ev.msg
        
        datapath = msg.datapath
        port = msg.match['in_port']
        pkt = packet.Packet(data=msg.data)
        #print(pkt)
        pkt_ethernet = pkt.get_protocol(ethernet.ethernet)
        if not pkt_ethernet:
            return
        
        pkt_lldp = pkt.get_protocol(lldp.lldp)
        if pkt_lldp:
            self.handle_lldp(datapath, port, pkt_ethernet, pkt_lldp)


    def handle_lldp(self, datapath, port, pkt_ethernet, pkt_lldp):
        self.lldp_topo.setdefault(datapath.id,{})
        port_connect = {}
        self.lldp_topo[datapath.id].setdefault(port, [pkt_lldp.tlvs[0].chassis_id, pkt_lldp.tlvs[1].port_id])
        print(datapath.id,pkt_lldp.tlvs[0].chassis_id,"Latency",(time.time())-(self.link_delay[int(datapath.id),int(port)]["start"]),"s")
         
#        print (self.lldp_topo)
         
       
       
    @set_ev_cls(ofp_event.EventOFPErrorMsg,MAIN_DISPATCHER)
    def error_msg_handler(self, ev):
        msg = ev.msg
        self.logger.debug('OFPErrorMsg received: type=0x%02x code=0x%02x message=%s',msg.type, msg.code, utils.hex_array(msg.data))