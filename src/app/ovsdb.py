# 2019
# Authour: Lu-Yi-Hsun
import time
import logging
import networkx as nx
import json
from utils import log, dict_tool
from gui import gui
from nested_dict import *

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
log.setup_logger(filename="app.log", maxBytes=0,
                 backupCount=0, level=logging.INFO)
log.Global_Log.info("dd")


class RinformanceRoute(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_5.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(RinformanceRoute, self).__init__(*args, **kwargs)
        self.echo_latency = {}
        self.datapaths = {}

        self.link_delay = {}
        self.switch_statistics = {}

        self.route_port = {}
        self.GUI_Mapping = []
        self.G = nx.Graph()
     
        # self._run_gui_htread=hub.spawn(self._run_gui)
        # self._update_gui_htread=hub.spawn(self._update_gui)
        """
        node spec
        len(ofp_multipart_type)==20
        
        self.G.nodes[$datapath.id] |["datapath"]=<Datapath object>
                                   |["port"]={$port_id:{"OFPMP_PORT_DESC":
                                                            {"port_no": 1, "length": 72, "hw_addr": "be:f3:b6:8a:f8:1e", "config": 0, "state": 4, "properties": [{"type": 0, "length": 32, "curr": 2112, "advertised": 0, "supported": 0, "peer": 0, "curr_speed": 10000000, "max_speed": 0}], "update_time": 1552314248.2066813}
                                                            },
                                                       "OFPMP_PORT_STATS":{dict}
                                                       }
                                             }
                                   |["all_port_duration"]=<class 'int'>#sec 'active working duration of all port '
                                   |["all_port_duration_temp"]=<class 'int'>#temp when del the port, a new port restart,                                                 #OFPMP_PORT_STATS's duration_sec will be zero
                                                 
                                                
        """
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
# ────────────────────────────────────────────────────────────────────────────────
    """SECTION Green Thread
    +-+-+-+-+-+ +-+-+-+-+-+-+
    |G|r|e|e|n| |T|h|r|e|a|d|
    +-+-+-+-+-+ +-+-+-+-+-+-+
    """
# ────────────────────────────────────────────────────────────────────────────────
 
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
        pass