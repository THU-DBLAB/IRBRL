from logging.handlers import RotatingFileHandler
import logging

import networkx as nx
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


relative_path="utils/log_file/"
"""
sdsa
"""
Global_Log ={}
"""
dd
"""

"""https://docs.python.org/3/library/logging.html#logrecord-attributes
set_Formatter
"""
def setup_logger(filename, maxBytes, backupCount, level=logging.INFO,set_Formatter='%(asctime)s %(levelname)s:%(message)s %(filename)s %(lineno)s  %(funcName)s() %(processName)s %(process)d %(threadName)s %(thread)d'):
    formatter = logging.Formatter(set_Formatter)
    relative_path_filename = relative_path+filename
    handler = RotatingFileHandler(
        filename=relative_path_filename, maxBytes=maxBytes, backupCount=backupCount)
    handler.setFormatter(formatter)

    logger = logging.getLogger("root")
    logger.setLevel(level)
    logger.addHandler(handler)
    global Global_Log
    Global_Log[filename] = logger

"""
log.setup_logger(filename="app.log", maxBytes=0,
                 backupCount=0, level=logging.INFO)
log.Global_Log["app.log"].info("dd")
"""
