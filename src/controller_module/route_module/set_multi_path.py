from controller_module import GLOBAL_VALUE
from controller_module import OFPT_FLOW_MOD
from controller_module.route_module import prioritylib
from nested_dict import *
from ryu.lib.packet import ether_types 
import networkx as nx
from ryu.lib import hub
import time
from controller_module import OFPT_FLOW_MOD,OFPT_PACKET_OUT,OFPT_GROUP_MOD
def setting_multi_route_path(self, route_path_list, weight_list, dst, prev_path=[],prev_weight=[],tos=0,idle_timeout=0,hard_timeout=0, delivery_schemes="unicast"):
        """
        這個版本比較笨需要全部刪除才能重新設定

        .. mermaid::

            graph TD
                Start --> 確保沒有其他線程正在設定dst_ip,tos的路徑
                確保沒有其他線程正在設定dst_ip,tos的路徑-->|否|確保沒有其他線程正在設定dst_ip,tos的路徑
                確保沒有其他線程正在設定dst_ip,tos的路徑-->|是|計算多條路權重合併
                計算多條路權重合併-->刪除dst_ip與tos的所有路徑
                刪除dst_ip與tos的所有路徑 -->  尋找所有岔路
                尋找所有岔路 --> 設定所有group[設定所有group entry]
                設定所有group[設定所有group entry] --> 設定非起點的flow[設定非起點的flow entry]
                設定非起點的flow[設定非起點的flow entry] --> 設定起點的flow[設定起點的flow entry]
                設定起點的flow[設定起點的flow entry] --> End

        .. mermaid::
        
            sequenceDiagram
                Title: 設定mulipath路徑流程
                autonumber
                交換機->>控制器: ofp_packet_in(flow table發生table miss的封包) 
                控制器->>控制器: 依照封包的tos去選擇,不同Qos設計出來的拓樸權重,該權重利用強化學習優化
                控制器->>交換機: ofp_group_mod(如果有岔路就需要設定group entry)

                rect rgba(0, 0, 255, .1)
                控制器->>+交換機: OFPT_BARRIER_REQUEST(確認先前設定已經完成)
                交換機->>-控制器: OFPT_BARRIER_REPLY(當完成設定就會回傳)
                Note over 交換機,控制器: 確保group entry設定完成
                end
                控制器->>交換機: ofp_flow_mod(設定非起點的flow entry,如果有岔路就需要設定group id)

                rect rgba(0, 0, 255, .1)
                控制器->>+交換機: OFPT_BARRIER_REQUEST(確認先前設定已經完成)
                交換機->>-控制器: OFPT_BARRIER_REPLY(當完成設定就會回傳)
                Note over 交換機,控制器: 確保非起點的flow entry設定完成
                end
                控制器->>交換機: ofp_flow_mod(設定起點的flow entry,如果有岔路就需要設定group id)
        """
        #確保不為空
        if route_path_list==[]:
            return

        all_mod=[]
        #route_path_list 必須保證free loop
        priority,dscp=prioritylib.tos_base(tos)
        #print(dst,priority)
        _cookie = GLOBAL_VALUE.get_cookie(dst,priority)
        
        for path, weight in zip(route_path_list, weight_list):
            a=""
            for i in path[2::3]:
                a=a+"->"+str(i)
            #print(a)
        # https://osrg.github.io/ryu-book/zh_tw/html/spanning_tree.html
        # delivery_schemes https://en.wikipedia.org/wiki/Routing#Delivery_schemes
        # 單播多路徑unicast
        # FIXME 未來開發多播multicast dst     可能要很多個?
        # 多條路徑(route_path_list)結合每個路徑的權重(weight_list)
        # weight_list[0]代表route_path_list[0]的權重 以此類推
        # 探討group如何select bucket
        # flow_mask_hash_fields    https://github.com/openvswitch/ovs/blob/v2.15.0/lib/flow.c#L2462
        # pick_default_select_group https://github.com/openvswitch/ovs/blob/v2.15.0/ofproto/ofproto-dpif-xlate.c#L4564
        # group_best_live_bucket https://github.com/openvswitch/ovs/blob/v2.15.0/ofproto/ofproto-dpif-xlate.c#L1956
        
         
        print("載入原先的路徑")
        for path,weight in zip(prev_path,prev_weight):
            route_path_list.append(path)
            weight_list.append(weight)
        #紀錄每個交換機需要OUTPUT的
        print("紀錄每個交換機需要OUTPUT的")
        _switch = nested_dict(2,dict)
        for path, weight in zip(route_path_list, weight_list): 
            for i in path[2::3]:
                set_datapath_id = i[0]
                set_out_port = i[1]
                if _switch[set_datapath_id][set_out_port]!={}:
                    #FIXME 多條路線經過同的路徑 權重利用平均 最小數值為1
                    _switch[set_datapath_id][set_out_port] = max(int((_switch[set_datapath_id][set_out_port]+weight)/2),1)
                else:
                    _switch[set_datapath_id][set_out_port] = weight
        print("刪除光原先的group entry flow entry重新設定")
        #刪除光原先的group entry flow entry重新設定
        self.clear_multi_route_path(dst, priority)
        time.sleep(GLOBAL_VALUE.setting_path_delay)#這邊假定d

        print("設定只有岔路需要設定group entry")
        #設定只有岔路需要設定group entry
        set_switch_for_barrier=set()
        for set_datapath_id in _switch:
            tmp_datapath = GLOBAL_VALUE.G.nodes[(set_datapath_id, None)]["datapath"]
            ofp = tmp_datapath.ofproto
            parser = tmp_datapath.ofproto_parser
            #       交換機出路大於2大表有岔路               and  此交換機還沒設定過group entry
            if len(_switch[set_datapath_id].keys()) >= 2 and set_datapath_id not in set_switch_for_barrier:
                port_list = list(_switch[set_datapath_id].keys())
                group_weight_list = []
                for p in list(_switch[set_datapath_id].keys()):
                    group_weight_list.append(_switch[set_datapath_id][p])
                group_mod=OFPT_GROUP_MOD.send_add_group_mod_v1(tmp_datapath, port_list, group_weight_list, group_id=_cookie)
                all_mod.append(group_mod)
                set_switch_for_barrier.add(tmp_datapath)

        print("確保剛才group entry 設定完成這樣後面用到group entry的路線才不會錯誤")
        #確保剛才group entry 設定完成這樣後面用到group entry的路線才不會錯誤
        for tmp_datapath in set_switch_for_barrier:
            self.wait_finish_switch_BARRIER_finish(tmp_datapath)
        
        #開始設定除了起點的flow entry
        print("開始設定除了起點的flow entry")
        set_switch_for_barrier=set()
        for path, weight in zip(route_path_list, weight_list):
            for i in path[5::3]:
                set_datapath_id = i[0]
                set_out_port = i[1]
                tmp_datapath = GLOBAL_VALUE.G.nodes[(
                    set_datapath_id, None)]["datapath"]
                set_switch_for_barrier.add(tmp_datapath)
                ofp = tmp_datapath.ofproto
                parser = tmp_datapath.ofproto_parser
                match = parser.OFPMatch(
                    eth_type=ether_types.ETH_TYPE_IP, ipv4_dst=dst,ip_dscp=dscp)
                if len(_switch[set_datapath_id].keys()) >= 2:
                    #有岔路需要group entry
                    action = [parser.OFPActionGroup(group_id=_cookie)]
                    instruction = [parser.OFPInstructionActions(
                        ofp.OFPIT_APPLY_ACTIONS, action)]
                    mod = parser.OFPFlowMod(datapath=tmp_datapath,
                                            priority=priority, table_id=2,
                                            command=ofp.OFPFC_ADD,
                                            match=match, cookie=_cookie,
                                            instructions=instruction, idle_timeout=idle_timeout,hard_timeout=hard_timeout
                                            )
                    all_mod.append(mod)
                    OFPT_FLOW_MOD.send_ADD_FlowMod(mod)
                else:
                    #沒有岔路不需要group entry
                    action = [parser.OFPActionOutput(port=set_out_port)]
                    instruction = [parser.OFPInstructionActions(
                        ofp.OFPIT_APPLY_ACTIONS, action)]
                    mod = parser.OFPFlowMod(datapath=tmp_datapath,
                                            priority=priority, table_id=2,
                                            command=ofp.OFPFC_ADD,
                                            match=match, cookie=_cookie,
                                            instructions=instruction, idle_timeout=idle_timeout,hard_timeout=hard_timeout
                                            )
                    all_mod.append(mod)
                    OFPT_FLOW_MOD.send_ADD_FlowMod(mod)
        #確保已經設定
        print("確保已經設定")
        for tmp_datapath in set_switch_for_barrier:
            self.wait_finish_switch_BARRIER_finish(tmp_datapath)
        set_switch_for_barrier=set()
        #全部設定完成 才能開始設定開頭的路線
        print("全部設定完成 才能開始設定開頭的路線")
        for path, weight in zip(route_path_list, weight_list):
            i =path[2]#開頭
            set_datapath_id = i[0]
            set_out_port = i[1]
            tmp_datapath = GLOBAL_VALUE.G.nodes[(
                set_datapath_id, None)]["datapath"]
            set_switch_for_barrier.add(tmp_datapath)
            ofp = tmp_datapath.ofproto
            parser = tmp_datapath.ofproto_parser
            match = parser.OFPMatch(
                eth_type=ether_types.ETH_TYPE_IP, ipv4_dst=dst,ip_dscp=dscp)
            if len(_switch[set_datapath_id].keys()) >= 2:
                action = [parser.OFPActionGroup(group_id=_cookie)]
                instruction = [parser.OFPInstructionActions(
                    ofp.OFPIT_APPLY_ACTIONS, action)]
                all_mod.append(mod)
                mod = parser.OFPFlowMod(datapath=tmp_datapath,
                                        priority=priority, table_id=2,
                                        command=ofp.OFPFC_ADD,
                                        match=match, cookie=_cookie,
                                        instructions=instruction, idle_timeout=idle_timeout,hard_timeout=hard_timeout
                                        )
                all_mod.append(mod)
                OFPT_FLOW_MOD.send_ADD_FlowMod(mod)
            else:
                action = [parser.OFPActionOutput(port=set_out_port)]
                instruction = [parser.OFPInstructionActions(
                    ofp.OFPIT_APPLY_ACTIONS, action)]
                mod = parser.OFPFlowMod(datapath=tmp_datapath,
                                        priority=priority, table_id=2,
                                        command=ofp.OFPFC_ADD,
                                        match=match, cookie=_cookie,
                                        instructions=instruction, idle_timeout=idle_timeout,hard_timeout=hard_timeout
                                        )
                all_mod.append(mod)
                OFPT_FLOW_MOD.send_ADD_FlowMod(mod)
        print("BARRIER 全部設定完成")
        for tmp_datapath in set_switch_for_barrier:
            self.wait_finish_switch_BARRIER_finish(tmp_datapath)
        print("BARRIER finish 全部設定完成")
        # FIXME 這個數值有最大值 需要回收
        GLOBAL_VALUE.PATH[dst][priority]["cookie"]=_cookie
        if GLOBAL_VALUE.PATH[dst][priority]["path"]=={}:
            GLOBAL_VALUE.PATH[dst][priority]["path"]=[]
        if GLOBAL_VALUE.PATH[dst][priority]["weight"]=={}:
            GLOBAL_VALUE.PATH[dst][priority]["weight"]=[]
         
        for p,w in zip(route_path_list,weight_list):
            if p not in GLOBAL_VALUE.PATH[dst][priority]["path"]:
                GLOBAL_VALUE.PATH[dst][priority]["path"].append(p)
                GLOBAL_VALUE.PATH[dst][priority]["weight"].append(w)

         
        if GLOBAL_VALUE.PATH[dst][priority]["graph"]=={}:
            GLOBAL_VALUE.PATH[dst][priority]["graph"]=nx.DiGraph()

        for path in route_path_list:   
            prev_node=None
            for node in path:  
                if prev_node!=None:
                    if GLOBAL_VALUE.PATH[dst][priority]["graph"]=={}:
                        GLOBAL_VALUE.PATH[dst][priority]["graph"]=nx.DiGraph()
                    GLOBAL_VALUE.PATH[dst][priority]["graph"].add_edge(prev_node, node, weight=1)    
                prev_node=node 
        #print(all_mod)
        return all_mod

def path_to_openflow_control_message(self, route_path_list, weight_list, dst,tos=0,idle_timeout=0,hard_timeout=0):
    """
    負責轉化路徑到控制訊息
    route_path_list組合出來的多路徑必須要事先保證free loop
    """
    all_flow_mod=[]
    all_group_mod=[]
    #route_path_list 必須保證free loop

    priority,_=prioritylib.tos_base(tos)
     
    #紀錄每個交換機需要OUTPUT的數量
    _switch = nested_dict(2,dict)
    for path, weight in zip(route_path_list, weight_list): 
        for i in path[2::3]:
            set_datapath_id = i[0]
            set_out_port = i[1]
            #_switch[set_datapath_id][set_out_port]代表流量從交換機(set_datapath_id)的port(set_out_port)出去的比率
            if _switch[set_datapath_id][set_out_port]!={}:
                #FIXME 多條路線經過同的路徑 權重利用平均 最小數值為1
                _switch[set_datapath_id][set_out_port] = max(int((_switch[set_datapath_id][set_out_port]+weight)/2),1)
            else:
                _switch[set_datapath_id][set_out_port] = weight

    #設定只有岔路需要設定group entry
    for set_datapath_id in _switch:
        tmp_datapath = GLOBAL_VALUE.G.nodes[(set_datapath_id, None)]["datapath"]
        ofp = tmp_datapath.ofproto
        parser = tmp_datapath.ofproto_parser
        if len(_switch[set_datapath_id].keys()) >= 2:
            port_list = list(_switch[set_datapath_id].keys())
            group_weight_list = []
            for p in list(_switch[set_datapath_id].keys()):
                group_weight_list.append(_switch[set_datapath_id][p])
            group_mod=OFPT_GROUP_MOD.send_add_group_mod_v1(tmp_datapath, port_list, group_weight_list, group_id=_cookie,dry_run=True)
            all_group_mod.append(group_mod)
    #解析所有需要傳送的flow mod
    for path, weight in zip(route_path_list, weight_list):
        for i in path[2::3]:
            set_datapath_id = i[0]
            set_out_port = i[1]
            tmp_datapath = GLOBAL_VALUE.G.nodes[(
                set_datapath_id, None)]["datapath"]
            ofp = tmp_datapath.ofproto
            parser = tmp_datapath.ofproto_parser
            match = parser.OFPMatch(
                eth_type=ether_types.ETH_TYPE_IP, ipv4_dst=dst,ip_dscp=dscp)
            if len(_switch[set_datapath_id].keys()) >= 2:
                #當遇到岔路flow entry需要指定到group table
                action = [parser.OFPActionGroup(group_id=_cookie)]
                instruction = [parser.OFPInstructionActions(
                    ofp.OFPIT_APPLY_ACTIONS, action)]
                mod = parser.OFPFlowMod(datapath=tmp_datapath,
                                        priority=priority, table_id=2,
                                        command=ofp.OFPFC_ADD,
                                        match=match, cookie=_cookie,
                                        instructions=instruction, idle_timeout=idle_timeout,hard_timeout=hard_timeout
                                        )
                all_flow_mod.append(mod)
            else:
                action = [parser.OFPActionOutput(port=set_out_port)]
                instruction = [parser.OFPInstructionActions(
                    ofp.OFPIT_APPLY_ACTIONS, action)]
                mod = parser.OFPFlowMod(datapath=tmp_datapath,
                                        priority=priority, table_id=2,
                                        command=ofp.OFPFC_ADD,
                                        match=match, cookie=_cookie,
                                        instructions=instruction, idle_timeout=idle_timeout,hard_timeout=hard_timeout
                                        )
                all_flow_mod.append(mod)
                    
  
    return all_flow_mod,all_group_mod

def get_current_flow_group_entry(self,dst,priority):
    """
    根據dst ip與priority優先權 拿到目前網路已經設定的flow entry
    """
    all_flow_mod=[]
    all_group_mod=[]
    _cookie_id=GLOBAL_VALUE.get_cookie(dst,priority)
    for datapath_id in GLOBAL_VALUE.G.nodes:
        #搜尋
        if  _cookie_id in GLOBAL_VALUE.G.nodes[(datapath_id, None)]["GROUP_TABLE"]:
            all_group_mod.append(GLOBAL_VALUE.G.nodes[(datapath_id, None)]["GROUP_TABLE"][_cookie_id])
        for match in GLOBAL_VALUE.G.nodes[(datapath_id, None)]["FLOW_TABLE"][2][priority]:
            mod=GLOBAL_VALUE.G.nodes[(datapath.id, None)]["FLOW_TABLE"][2][priority][match]
            try:
                ipv4_dst = msg.match.get("ipv4_dst")
                if ipv4_dst==dst:
                    all_flow_mod.append(mod)
            except:
                pass    
    return all_flow_mod,all_group_mod


def setting_multi_route_path_base_auto_compare(self, route_path_list, weight_list, dst,tos=0,idle_timeout=0,hard_timeout=0):
    """
    這裡的方案會自動比較所有flow entry 與group entry只更新刪除需要的部份
    """
    new_all_flow_mod,new_all_group_mod=path_to_openflow_control_message(self,route_path_list, weight_list, dst,tos,idle_timeout,hard_timeout)

    old_all_flow_mod,old_all_group_mod=get_current_flow_group_entry(dst,priority=prioritylib.tos_base(tos))

    #需要先處理gorup table更新
    #確認group table更新已經完成
    #開始更新flow table
    for mod in new_all_flow_mod:
        if mod not in old_all_flow_mod:
            pass


    pass

    
    
     
   