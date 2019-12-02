# Copyright (C) 2011 Nippon Telegraph and Telephone Corporation.

#

# Licensed under the Apache License, Version 2.0 (the "License");

# you may not use this file except in compliance with the License.

# You may obtain a copy of the License at

#

#    http://www.apache.org/licenses/LICENSE-2.0

#

# Unless required by applicable law or agreed to in writing, software

# distributed under the License is distributed on an "AS IS" BASIS,

# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or

# implied.

# See the License for the specific language governing permissions and

# limitations under the License.

 

from ryu.base import app_manager

from ryu.controller import ofp_event

from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER

from ryu.controller.handler import set_ev_cls

from ryu.ofproto import ofproto_v1_3

from ryu.lib.packet import packet

from ryu.lib.packet import ethernet

 

 

class SimpleSwitch13(app_manager.RyuApp):

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

 

    def __init__(self, *args, **kwargs):

        super(SimpleSwitch13, self).__init__(*args, **kwargs)

        self.mac_to_port = {}

 

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)

    def switch_features_handler(self, ev):

        datapath = ev.msg.datapath

        ofproto = datapath.ofproto

        parser = datapath.ofproto_parser

 

        # install table-miss flow entry

        #

        # We specify NO BUFFER to max_len of the output action due to

        # OVS bug. At this moment, if we specify a lesser number, e.g.,

        # 128, OVS will send Packet-In with invalid buffer_id and

        # truncated packet data. In that case, we cannot output packets

        # correctly.  The bug has been fixed in OVS v2.1.0.

        match = parser.OFPMatch()

        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,

                                          ofproto.OFPCML_NO_BUFFER)]

        self.add_flow(datapath, 0, match, actions)

       

        # add rule for metering in s1

        if ev.msg.datapath.id==1:

          datapath = ev.msg.datapath

          ofproto = datapath.ofproto

          parser = datapath.ofproto_parser

 

          bands = [parser.OFPMeterBandDrop(type_=ofproto.OFPMBT_DROP, len_=0, rate=333, burst_size=10)]

 

          req=parser.OFPMeterMod(datapath=datapath, command=ofproto.OFPMC_ADD, flags=ofproto.OFPMF_KBPS, meter_id=1, bands=bands)

         

          datapath.send_msg(req)

        

          #when the traffic generated from h1 will be applied to meter_id=1

          match = parser.OFPMatch(eth_type=0x0800, ip_dscp=(0b111000))

          actions = [parser.OFPActionOutput(2)]

          inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions), parser.OFPInstructionMeter(1,ofproto.OFPIT_METER)]

          mod = datapath.ofproto_parser.OFPFlowMod(

              datapath=datapath, match=match, cookie=0,

              command=ofproto.OFPFC_ADD, idle_timeout=0,  

              hard_timeout=0, priority=3, instructions=inst)

          datapath.send_msg(mod)

 

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):

        ofproto = datapath.ofproto

        parser = datapath.ofproto_parser

 

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,

                                             actions)]

        if buffer_id:

            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,

                                    priority=priority, match=match,

                                    instructions=inst)

        else:

            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,

                                    match=match, instructions=inst,hard_timeout=5)

        datapath.send_msg(mod)

 
      # SECTION OFPT_FLOW_REMOVED
    @set_ev_cls(ofp_event.EventOFPFlowRemoved, MAIN_DISPATCHER)
    def _flow_removed_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp = dp.ofproto
        print(msg.reason,"有人被刪除",msg)
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
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)

    def _packet_in_handler(self, ev):

        # If you hit this you might want to increase

        # the "miss_send_length" of your switch

        if ev.msg.msg_len < ev.msg.total_len:

            self.logger.debug("packet truncated: only %s of %s bytes",

                              ev.msg.msg_len, ev.msg.total_len)

        msg = ev.msg

        datapath = msg.datapath

        ofproto = datapath.ofproto

        parser = datapath.ofproto_parser

        in_port = msg.match['in_port']

 

        pkt = packet.Packet(msg.data)

        eth = pkt.get_protocols(ethernet.ethernet)[0]

 

        dst = eth.dst

        src = eth.src

 

        dpid = datapath.id

        self.mac_to_port.setdefault(dpid, {})

 

        self.logger.info("packet in %s %s %s %s", dpid, src, dst, in_port)

 

        # learn a mac address to avoid FLOOD next time.

        self.mac_to_port[dpid][src] = in_port

 

        if dst in self.mac_to_port[dpid]:

            out_port = self.mac_to_port[dpid][dst]

        else:

            out_port = ofproto.OFPP_FLOOD

 

        actions = [parser.OFPActionOutput(out_port)]

 

        # install a flow to avoid packet_in next time

        if out_port != ofproto.OFPP_FLOOD:

            match = parser.OFPMatch(in_port=in_port, eth_dst=dst)

            # verify if we have a valid buffer_id, if yes avoid to send both

            # flow_mod & packet_out

            if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                print(msg.buffer_id,"msg.buffer_idmsg.buffer_idmsg.buffer_idmsg.buffer_id")

                self.add_flow(datapath, 1, match, actions, msg.buffer_id)

                return

            else:

                self.add_flow(datapath, 1, match, actions)

        data = None

        if msg.buffer_id == ofproto.OFP_NO_BUFFER:

            data = msg.data

 

        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,

                                  in_port=in_port, actions=actions, data=data)

        datapath.send_msg(out)