
from controller_module import GLOBAL_VALUE 


def send_ADD_FlowMod(self, mod):
    datapath = mod.datapath
    OFPFlowMod = mod.__dict__
    table_id = OFPFlowMod["table_id"]
    match = OFPFlowMod["match"]
    priority = OFPFlowMod["priority"]
    ofp = datapath.ofproto
    # 要交換機當flow entry被刪除都要通知控制器
    mod.flags = ofp.OFPFF_SEND_FLOW_REM
    # if self._check_no_overlap_on_server(datapath.id,table_id,priority,match):
    mod.xid = GLOBAL_VALUE.get_xid(datapath.id)

    GLOBAL_VALUE.G.nodes[(datapath.id, None)
                    ]["FLOW_TABLE"][table_id][priority][str(match)] = mod
    self.error_search_by_xid[datapath.id][mod.xid]=mod
    datapath.send_msg(mod)
    #    return True
    return False