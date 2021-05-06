from ryu.ofproto import ofproto_v1_5
from ryu.lib.packet import ether_types, in_proto, icmpv6
import networkx as nx
from networkx.classes.function import path_weight
def send_add_group_mod(self, datapath, port_list: list, weight_list: list,vlan_tag_list:list, group_id: int):
        """
        group_id是給flow entry指引要導到哪個group entry
        """
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser
        buckets = []
        # Each bucket of the group must have an unique Bucket ID-openflow1.51-p115 所以亂給個id給它 反正我沒用到
        bucket_id = 0
        for port, weight,vlan_vid in zip(port_list, weight_list,vlan_tag_list):
            #bucket_id=self.G.nodes[(datapath.id,None)]["now_max_group_id"]
            assert 1<=vlan_vid<=4095,"vlan_vid range need in 1~4095"#vlan_vid 1~4095
            
            vlan_tci=ofproto_v1_5.OFPVID_PRESENT+vlan_vid#spec openflow1.5.1 p.82,你要多加這個openvswitch才知道你要設定vlan_vid
            """
            enum ofp_vlan_id { 
                OFPVID_PRESENT = 0x1000, /* Bit that indicate that a VLAN id is set */ 
                OFPVID_NONE = 0x0000, /* No VLAN id was set. */
            };
            """
            #三個動作1.Push VLAN header" 2."Set-Field VLAN_VID value"3."Output port" 
            actions = [ofp_parser.OFPActionPushVlan(self.MultiPath_Slicing_EtherType),ofp_parser.OFPActionSetField(vlan_vid=vlan_tci),ofp_parser.OFPActionOutput(port)]
            # spec openflow1.5.1 p.116  struct ofp_group_bucket_prop_weight
            # 注意ryu ofv1.5.1的group範例寫錯
            # 下面這個寫法要靠自己挖ryu原始碼才寫出來,所以遇到問題盡量挖控制器ryu,openvswitch原始碼
            # ofp_bucket->properties->ofp_group_bucket_prop_weight-spec openflow1.5.1 p.115~p.116
            _weight = ofp_parser.OFPGroupBucketPropWeight(
                weight=weight, length=8, type_=ofp.OFPGBPT_WEIGHT)
            buckets.append(ofp_parser.OFPBucket(
                bucket_id=bucket_id, actions=actions, properties=[_weight]))
            bucket_id = bucket_id+1
            #print("bucket_id",bucket_id)
            self.G.nodes[(datapath.id, None)]["now_max_group_id"] = self.G.nodes[(
                datapath.id, None)]["now_max_group_id"]+1
        # 從多個路線根據權重(weight)隨機從buckets選一個OFPBucket(ofp.OFPGT_SELECT),OFPBucket裡面就放要actions要出去哪個port
        mod = ofp_parser.OFPGroupMod(datapath, command=ofp.OFPGC_ADD,
                                     type_=ofp.OFPGT_SELECT, group_id=group_id, buckets=buckets)
        mod.xid = self.G.nodes[(datapath.id, None)]["now_max_xid"]
        #print(mod.xid,mod)
        self.G.nodes[(datapath.id, None)]["now_max_xid"] = self.G.nodes[(
            datapath.id, None)]["now_max_xid"]+1
        datapath.send_msg(mod)

def send_add_group_mod_v1(self, datapath,port_list:list,weight_list:list,group_id:int):
     
    assert all(isinstance(x, int) for x in weight_list),"send_add_group_mod_v1 weight_list必須都是整數"+str(weight_list)
    """
    group_id是給flow entry指引要導到哪個group entry
    """
    ofp = datapath.ofproto
    ofp_parser = datapath.ofproto_parser
    buckets=[]
    #Each bucket of the group must have an unique Bucket ID-openflow1.51-p115 所以亂給個id給它 反正我沒用到
    bucket_id=1
    for port,weight in zip(port_list,weight_list):
        #bucket_id=self.G.nodes[(datapath.id,None)]["now_max_group_id"]
        actions = [ofp_parser.OFPActionOutput(port)]
        #spec openflow1.5.1 p.116  struct ofp_group_bucket_prop_weight
        #注意ryu ofv1.5.1的group範例寫錯
        #下面這個寫法要靠自己挖ryu原始碼才寫出來,所以遇到問題盡量挖控制器ryu,openvswitch原始碼
        #ofp_bucket->properties->ofp_group_bucket_prop_weight-spec openflow1.5.1 p.115~p.116 
        _weight=ofp_parser.OFPGroupBucketPropWeight(weight=weight,length=8,type_=ofp.OFPGBPT_WEIGHT)
        buckets.append(ofp_parser.OFPBucket(bucket_id=bucket_id,actions=actions,properties=[_weight]))
        bucket_id=bucket_id+1
    
    #self.G.nodes[(datapath.id,None)]["now_max_group_id"]=self.G.nodes[(datapath.id,None)]["now_max_group_id"]+1
    #從多個路線根據權重(weight)隨機從buckets選一個OFPBucket(ofp.OFPGT_SELECT),OFPBucket裡面就放要actions要出去哪個port
     
    command=None
    if self.G.nodes[(datapath.id,None)]["GROUP_TABLE"][group_id]=={}:
        command=ofp.OFPGC_ADD
    else:
        command=ofp.OFPGC_MODIFY

    mod = ofp_parser.OFPGroupMod(datapath, command=command,type_=ofp.OFPGT_SELECT, group_id=group_id, buckets=buckets)
    mod.xid=self.get_xid(datapath.id)
    datapath.send_msg(mod)
    self.G.nodes[(datapath.id,None)]["GROUP_TABLE"][group_id]=mod

    self.error_search_by_xid[datapath.id][mod.xid]=mod


def setting_multi_route_path_base_vlan(self, route_path_list, weight_list, ipv4_dst, ipv4_src):
        #利用vlan tag把每個simple path切開
        #舉例有5條路線
        #起始:一開始起點交換機就要從group entry裡面5個bucket選擇一個bucket,每個bucket代表某一條simple path,bucket做三個動作 1."Push VLAN header" 2."Set-Field VLAN_VID value"3."Output port" VLAN_VID為此simple path push vlan tag
        #中間:路由根據src dst vlan_id 去路由
        #最後:終點交換機要pop vlan tag才丟給host
        """
        非常重要要注意要清楚 vlan運作模式
        不管有沒有塞入vlan,ethertype永遠不變,只會向後擠
        還沒塞入vlan
        |dst-mac|src-mac|ethertype|payload
        塞入vlan
        |dst-mac|src-mac|0x8100|tci|ethertype|payload
        """
        priority=2
        idle_timeout=5
        _cookie = self.get_cookie()
        vlan_tag=1
        for path in route_path_list:
            vlan_tci=ofproto_v1_5.OFPVID_PRESENT+vlan_tag#spec openflow1.5.1 p.82,你要多加這個openvswitch才知道你要設定vlan_vid
            #path:[(1, 4), (1, None), (1, 2), (3, 1), (3, None), (3, 2), (4, 2), (4, None), (4, 3)]
            for index,i in enumerate(path[5::3]):
                set_datapath_id = i[0]
                set_out_port = i[1]
                tmp_datapath = self.G.nodes[(set_datapath_id, None)]["datapath"]
                ofp = tmp_datapath.ofproto
                parser = tmp_datapath.ofproto_parser  
                if index==(len(path)/3)-2:
                    #最後
                    #print("最後")
                    match = parser.OFPMatch(
                    eth_type=ether_types.ETH_TYPE_IP, vlan_vid=vlan_tci,ipv4_src=ipv4_src,ipv4_dst=ipv4_dst)
                    action_set = [parser.OFPActionPopVlan(),parser.OFPActionOutput(port=set_out_port)]
                    instruction = [parser.OFPInstructionActions(
                        ofp.OFPIT_APPLY_ACTIONS, action_set)]
                    mod = parser.OFPFlowMod(datapath=tmp_datapath,
                                            priority=priority, table_id=2,
                                            command=ofp.OFPFC_ADD,
                                            match=match, cookie=_cookie,
                                            instructions=instruction, idle_timeout=idle_timeout
                                            )
                    self._send_ADD_FlowMod(mod)
                else:
                    #中間
                    #print("中間")
                    match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP, vlan_vid=vlan_tci,ipv4_dst=ipv4_dst,ipv4_src=ipv4_src)
                    action = [parser.OFPActionOutput(port=set_out_port)]
                    instruction = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, action)]
                    mod = parser.OFPFlowMod(datapath=tmp_datapath,
                                            priority=priority, table_id=2,
                                            command=ofp.OFPFC_ADD,
                                            match=match, cookie=_cookie,
                                            instructions=instruction, idle_timeout=idle_timeout
                                            )
                    self._send_ADD_FlowMod(mod)
            vlan_tag=vlan_tag+1
        #起始
        port_list=[]
        vlan_tag=[]
        vlan_index=1
        for path in route_path_list:
            i=path[2]
            set_datapath_id = i[0]
            set_out_port = i[1]
            port_list.append(set_out_port)
            tmp_datapath = self.G.nodes[(set_datapath_id, None)]["datapath"]
            vlan_tag.append(vlan_index)
            vlan_index=vlan_index+1
            #保證剛才路徑設定完成
            self.wait_finish_switch_BARRIER_finish(tmp_datapath)
        ofp = tmp_datapath.ofproto
        parser = tmp_datapath.ofproto_parser
        send_add_group_mod(self,tmp_datapath, port_list, weight_list,vlan_tag_list=vlan_tag,group_id=_cookie)

        #確保先前的所有設定已經完成,才能開始設定起點的flow table
        #如果不確保會導致封包已經開始傳送但是路徑尚未設定完成的錯誤

        #保證group 設定完成
        self.wait_finish_switch_BARRIER_finish(tmp_datapath)
        match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP,ipv4_dst=ipv4_dst,ipv4_src=ipv4_src)
        action = [parser.OFPActionGroup(group_id=_cookie)]
        instruction = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, action)]
        mod = parser.OFPFlowMod(datapath=tmp_datapath,
                                priority=priority, table_id=2,
                                command=ofp.OFPFC_ADD,
                                match=match, cookie=_cookie,
                                instructions=instruction, idle_timeout=idle_timeout
                                )
        self._send_ADD_FlowMod(mod)
        #上面都完成就紀錄
         
        self.PATH[ipv4_src][ipv4_dst]["cookie"][_cookie] = route_path_list
        #self.PATH[ipv4_src][ipv4_dst]["proitity"][priority] = _cookie

def Packout_to_FlowTable(tmp_datapath,data):
    ofp = tmp_datapath.ofproto
    parser = tmp_datapath.ofproto_parser
    match = tmp_datapath.ofproto_parser.OFPMatch(
        in_port=ofp.OFPP_CONTROLLER)
    actions = [parser.OFPActionOutput(port=ofp.OFPP_TABLE)]
    out = parser.OFPPacketOut(datapath=tmp_datapath, buffer_id=ofp.OFP_NO_BUFFER,
                                match=match, data=data,actions=actions)
    tmp_datapath.send_msg(out)

def Get_NOW_GRAPH(self,dst,priority):
    check_G = nx.DiGraph()

    if self.PATH[dst][priority]["path"]!={}:
        for path,weight in zip(self.PATH[dst][priority]["path"],self.PATH[dst][priority]["weight"]):
            prev_node=None
            for node in path:  
                if prev_node!=None:
                    check_G.add_edge(prev_node, node, weight=1)
                prev_node=node 
    return check_G

#--------------------------------
"""
底下的函數可以拿來產生路徑要餵食給setting_multi_route_path的參數

FIXME 需要補 演算法複雜度
"""
#--------------------------------
def k_shortest_path_loop_free_version(self,k,src_datapath_id,src_port,dst_datapath_id,dst_port,check_G=None,weight="weight"):
    #這個保證路徑沒有loop
    loop_free_path=[]
    path_length=[]
    loop_check=Loop_Free_Check(check_G)
    try:
        shortest_simple_paths=nx.shortest_simple_paths(self.G, (src_datapath_id, src_port), (dst_datapath_id, dst_port), weight=weight)
    except:
        return
    for path in shortest_simple_paths:
        if len(loop_free_path)==k:
            break
        prev_node=None
        for node in path:  
            if prev_node!=None:
                 
                loop_check.add_edge(prev_node, node, weight=self.G[prev_node][node][weight])
            prev_node=node 
        _check_free=loop_check.check_free_loop()
        if _check_free:
            loop_free_path.append(path)
            path_length.append(path_weight(self.G, path, weight=weight))
    
    return loop_free_path,path_length

class Loop_Free_Check():
    """
    負責確認是否出現環形路由
    """
    check_G = nx.DiGraph()
    tmp_check_G=None
    def __init__(self,check_G=None):
        if check_G!=None:
            self.check_G=check_G.copy()
        self.tmp_check_G=self.check_G.copy()
    def add_edge(self,prev_node,node,weight=None):
        "塞入edge到nx.DiGraph()"
        self.tmp_check_G.add_edge(prev_node, node, weight=weight)
         
    def check_free_loop(self):
        "塞入edge到nx.DiGraph()"
        try:
            nx.find_cycle(self.tmp_check_G, orientation="original")
            self.tmp_check_G=self.check_G
            print("!!!有還")
            exit(1)
            return False
        except:
            self.check_G=self.tmp_check_G
            return True

        

def k_shortest_path_first_and_maximum_flow_version(self,k,src_datapath_id,src_port,dst_datapath_id,dst_port,check_G=None,weight="weight"):
    #這個保證路徑沒有loop
    #當我們想要考量 最大剩餘頻寬 於鏈路cost如何合併? 
    loop_free_path=[]
    path_length=[]
    loop_check=Loop_Free_Check(check_G)
    for path in nx.shortest_simple_paths(self.G, (src_datapath_id, src_port), (dst_datapath_id, dst_port), weight=weight):
        if len(loop_free_path)==k:
            break
        prev_node=None
        for node in path:  
            if prev_node!=None:
                print(prev_node,node,weight)
                loop_check.add_edge(prev_node, node, weight=self.G[prev_node][node][weight])
            prev_node=node 
        _check_free=loop_check.check_free_loop()
        if _check_free:
            loop_free_path.append(path)
            path_length.append(path_weight(self.G, path, weight=weight))

     
    return loop_free_path,path_length


def k_maximum_flow_loop_free_version(self,k,src_datapath_id,src_port,dst_datapath_id,dst_port,check_G=None,weight="weight",capacity="capacity"):
    #這個保證路徑沒有loop
    #當我們想要考量 最大剩餘頻寬 於鏈路cost如何合併? 
    loop_free_path=[]
    path_length=[]
    tmp_G=self.G.copy()

    if check_G==None:
        check_G = nx.DiGraph()

    while len(loop_free_path)<k:
        try:
            maxflow=nx.maximum_flow(tmp_G,(src_datapath_id, src_port), (dst_datapath_id, dst_port),capacity=capacity)  
            
            _tmp_path=[]
            for node in maxflow:
                _tmp_path.append(node)
            loop_free_path.append(_tmp_path)


            G.remove_edge(0, 1)
        except:
            pass
            break


    return loop_free_path
        
    if check_G==None:
        check_G = nx.DiGraph()
    for path in nx.shortest_simple_paths(self.G, (src_datapath_id, src_port), (dst_datapath_id, dst_port), weight=weight):
        tmp_check_G=check_G.copy()
        if len(loop_free_path)==k:
            break
        prev_node=None
        for node in path:  
            if prev_node!=None:
                tmp_check_G.add_edge(prev_node, node, weight=self.G[prev_node][node][weight])
            prev_node=node 
        try:
            nx.find_cycle(tmp_check_G, orientation="original")
        except:
            check_G=tmp_check_G
            loop_free_path.append(path)
            path_length.append(path_weight(check_G, path, weight=weight))
    return loop_free_path,path_length


 


def ECMP_PATH(self,src_datapath_id,src_port,dst_datapath_id,dst_port,weight="weight"):
    """
    ecmp選擇多條cost與shortest path一樣的路徑
    """
    #ecmp選擇多條cost與shortest path一樣的路徑
    #會造成選擇不多樣
    #ecmp跟我們說這樣的條件會保證loop free所以不需要確認
    ok_path=[]
    best_length=0
    for idx,path in enumerate(nx.shortest_simple_paths(self.G, (src_datapath_id, src_port), (dst_datapath_id, dst_port), weight=weight)):
        if idx==0:
            best_length=path_weight(self.G, path, weight=weight)
            ok_path.append(path)
            continue
        if best_length==path_weight(self.G, path, weight=weight):
            ok_path.append(path)
        else:
            break      
    return ok_path,best_length