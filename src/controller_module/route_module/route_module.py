import ryu
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
import time
from nested_dict import *
import numpy as np
import networkx as nx
from networkx.classes.function import path_weight
from controller_module.utils import log, dict_tool
from controller_module import GLOBAL_VALUE
from controller_module import OFPT_FLOW_MOD,OFPT_PACKET_OUT,OFPT_GROUP_MOD
from controller_module.route_metrics import formula
from controller_module.route_module import prioritylib
from controller_module.route_module import path_select
from controller_module.route_module import set_multi_path
from controller_module.OFPT_PACKET_OUT import send_arp_packet,Packout_to_FlowTable
CONF = cfg.CONF


class RouteModule(app_manager.RyuApp):
    """負責處理被動路由與動態路由
 
    多路徑路由(src->dst)可能的問題
        當多條路徑 並不是每條路徑都會均勻的被走過導致某些路線會idle-timeout,路線被清除,如果剛好路線

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
    """
    OFP_VERSIONS = [ofproto_v1_5.OFP_VERSION]
   
    "一次只能有一個程式掌控網路"
 
    Qos_Select_Weight_Call_Back=None

    #這裡可以控制你要使用哪種路線選擇器
    path_selecter=None#path_select.k_shortest_path_loop_free_version
    #這裡可以控制你要用什麼機制動態更新
    Setting_Multi_Route_Path=set_multi_path.setting_multi_route_path

    def __init__(self, *args, **kwargs):
        
        
        self._active_route_thread = hub.spawn(self.active_route)
        
        super(RouteModule, self).__init__(*args, **kwargs)
    def _check_know_ip_place(self, ip):
        # 確保此ip位置知道在那
        if GLOBAL_VALUE.ip_get_datapathid_port[ip]["datapath_id"] == {} or GLOBAL_VALUE.ip_get_datapathid_port[ip]["port"]=={}:
            # 因為不知道此目的地 ip在哪個交換機的哪個port,所以需要暴力arp到處問
            OFPT_PACKET_OUT.arp_request_all(ip)
            # FIXME 這裡要注意迴圈引發問題 可能需要異步處理,arp只發一次
            # 這裡等待問完的結果
            print("check")
            while GLOBAL_VALUE.ip_get_datapathid_port[ip]["datapath_id"] == {} or GLOBAL_VALUE.ip_get_datapathid_port[ip]["port"]=={}:
                hub.sleep(0)
                # time.sleep(0.01)#如果沒有sleep會導致 整個系統停擺,可以有其他寫法？
            print("check ok")
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        """
        非同步接收來自交換機OFPT_PACKET_IN message
        """
        msg = ev.msg
        datapath = msg.datapath
        
        port = msg.match['in_port']
        pkt = packet.Packet(data=msg.data)
        pkt_ethernet = pkt.get_protocol(ethernet.ethernet)
        pkt_ipv4 = pkt.get_protocol(ipv4.ipv4)
        if pkt_ipv4:
            # table 2負責路由
            if msg.table_id == 2:
                print("拿到路由需求")
                # 想要路由但不知道路,我們需要幫它,這屬於被動路由
                hub.spawn(self.handle_route, datapath=datapath, port=port, msg=msg)  
    def get_alog_name_by_tos(self,dscp):
        "負責根據tos去選擇演算法"
        if self.Qos_Select_Weight_Call_Back!=None:
            alog=self.Qos_Select_Weight_Call_Back(dscp)
            return alog
        #default的演算法
        alog="weight"
        if dscp==0:
            alog = "low_delay"
        else:
            alog="low_jitter"
     
    def handle_route(self, datapath, port, msg):
        _start_time=time.time()
       
        print("------handle_route------")
         
        print("\n\n")
        
        GLOBAL_VALUE.route_control_sem.acquire()
        data = msg.data
        in_port = msg.match['in_port']

        pkt = packet.Packet(data=data)
        pkt_ethernet = pkt.get_protocol(ethernet.ethernet)
        pkt_ipv4 = pkt.get_protocol(ipv4.ipv4)
        #alog = "low_delay"  # EIGRP
        print("被動路由", pkt_ipv4.src,"->",pkt_ipv4.dst,"優先權",pkt_ipv4.tos,bin(pkt_ipv4.tos))
        
        priority,dscp=prioritylib.tos_base(pkt_ipv4.tos)
        #alog=self.get_alog_name_by_tos(dscp)
         
        #確保知道此ip的位置,下面這行再做,當不知道ip在哪個port與交換機,就需要利用arp prop序詢問
        self._check_know_ip_place(pkt_ipv4.src)
        self._check_know_ip_place(pkt_ipv4.dst)

        # 拿出目的地交換機id
        dst_datapath_id = GLOBAL_VALUE.ip_get_datapathid_port[pkt_ipv4.dst]["datapath_id"]
        # 拿出目的地port number
        dst_port = GLOBAL_VALUE.ip_get_datapathid_port[pkt_ipv4.dst]["port"]
        src_datapath_id = GLOBAL_VALUE.ip_get_datapathid_port[pkt_ipv4.src]["datapath_id"]
        # 拿出目的地port number
        src_port = GLOBAL_VALUE.ip_get_datapathid_port[pkt_ipv4.src]["port"]
        """
        在控制器的Queue有可能塞很多,需要路由到相同目的地的封包
        舉例
            兩個封包想要到達10.0.0.1,但是FLOW TABLE沒有設定,所以會轉送到控制器
            控制器的Queue上封包1,封包2都是要到10.0.0.1
            控制器看到封包1需要設定路線就開始處理
            此時FLOW TABLE已經知道如何轉送10.0.0.1
            但是控制器看到封包2又需要設定路線
            這樣會導致被動模塊頻繁更改路由,為了分工,被動模塊只負責設定未知路線的封包,動態路由只動態改變已設定好的路線
            為了避免重複設定與破壞分工,所以這裡負責確認路線是否已經設定完成就直接轉送
        """
        print("確認路線已經設定完成了嗎?")
        if self.check_route_setting(src_datapath_id,pkt_ipv4,priority):
            tmp_datapath = GLOBAL_VALUE.G.nodes[(src_datapath_id, None)]["datapath"]
            Packout_to_FlowTable(tmp_datapath,data)
            print("路線早已設定完成封包直接轉送回交換機")
            GLOBAL_VALUE.route_control_sem.release()#離開要補釋放資源
            return
        print("路線還沒設定,準備開始設定")
        #print("有")
        # 選出單一路徑
        print("拿出原先到達",pkt_ipv4.dst,"所有路徑")
        prev_G=Get_NOW_GRAPH(self,pkt_ipv4.dst,priority)
        print("拿到原先所有路徑加上後來新增的路徑並且確保不會發生LOOP")
        route_path_list_go,_=self.path_selecter(GLOBAL_VALUE.MAX_K_SELECT_PATH,src_datapath_id,src_port,dst_datapath_id,dst_port,check_G=prev_G,weight="weight")
        #print("確認是否有找到路徑",route_path_list_go)
        #發生找不道路徑
        if route_path_list_go==None:
            #找不到路徑 直接讓封包遺失
            GLOBAL_VALUE.route_control_sem.release()#離開要補釋放資源
            print("找不到路徑 任由封包遺失 handle_route離開")
            return

        weight_list_go = [1 for _ in range(len(route_path_list_go))]#權重全部1代表如果有多路徑 每條路線流量分配相等
        #print(GLOBAL_VALUE.PATH[pkt_ipv4.dst][priority]["path"])
        print("handle_route 開始設定路徑-----------\n\n")
        self.Setting_Multi_Route_Path(route_path_list_go, weight_list_go, pkt_ipv4.dst,idle_timeout=GLOBAL_VALUE.FLOW_ENTRY_IDLE_TIMEOUT,tos=pkt_ipv4.tos,prev_path=GLOBAL_VALUE.PATH[pkt_ipv4.dst][priority]["path"],prev_weight=GLOBAL_VALUE.PATH[pkt_ipv4.dst][priority]["weight"])
        # 上面只是規劃好路徑 這裡要幫 上來控制器詢問的`迷途小封包` 指引,防止等待rto等等...
        # 你可以測試下面刪除會導致每次pingall都要等待
        # 確保是有找到f路徑
        #把送上來未知的封包重新送回去路徑的起始點
        pkt = packet.Packet(data=data)
        tmp_datapath = GLOBAL_VALUE.G.nodes[(src_datapath_id, None)]["datapath"]
        print("把上來詢問控制器的封包轉送",tmp_datapath.id)
        Packout_to_FlowTable(tmp_datapath,data)
         
        GLOBAL_VALUE.route_control_sem.release()
        print("耗時:",time.time()-_start_time)
        print("設定完成\n\n\n")

    def check_route_setting(self,src_datapath_id,pkt_ipv4,priority):
        for path in GLOBAL_VALUE.PATH[pkt_ipv4.dst][priority]["path"]:
            i=path[2]
            set_datapath_id = i[0]
            if src_datapath_id==set_datapath_id:  
                print(path,src_datapath_id,pkt_ipv4) 
                return True
        return False

    def clear_multi_route_path(self,dst, priority):
        """
        刪除乾淨dst
        """
        #假定已經刪除乾淨
        del GLOBAL_VALUE.PATH[dst][priority]["path"]

        set_switch_for_barrier=set()
        if GLOBAL_VALUE.PATH[dst][priority]["path"]!={}:
            cookie=GLOBAL_VALUE.PATH[dst][priority]["cookie"]
            #保證cookie 0不會倍刪除
            if cookie==0:
                return
            for path in GLOBAL_VALUE.PATH[dst][priority]["path"]:
                for i in path[2::3]:
                    set_datapath_id = i[0]
                    tmp_datapath = GLOBAL_VALUE.G.nodes[(set_datapath_id, None)]["datapath"]
                    ofp = tmp_datapath.ofproto
                    parser = tmp_datapath.ofproto_parser
                    
                    mod = parser.OFPGroupMod(tmp_datapath, command=ofp.OFPGC_DELETE,group_id=cookie)
                     
                    tmp_datapath.send_msg(mod)
                    
                    match = parser.OFPMatch()
                    mod = parser.OFPFlowMod(datapath=tmp_datapath, table_id=ofp.OFPTT_ALL,
                                            command=ofp.OFPFC_DELETE, out_port=ofp.OFPP_ANY, out_group=ofp.OFPG_ANY,
                                            match=match, cookie=cookie, cookie_mask=0xffffffffffffffff
                                            )
                    
                    
                    tmp_datapath.send_msg(mod)
                    
                    set_switch_for_barrier.add(tmp_datapath)
        print("clear_multi_route_path 等待刪除乾淨")
        for tmp_datapath in set_switch_for_barrier:
            self.wait_finish_switch_BARRIER_finish(tmp_datapath)
        print("clear_multi_route_path 刪除乾淨")
        
         

    def send_barrier_request(self, datapath,xid=None):
        ofp_parser = datapath.ofproto_parser
        req = ofp_parser.OFPBarrierRequest(datapath)
        req.xid=xid
        datapath.send_msg(req)
    #當交換機已經完成先前的設定才會回傳這個
    @set_ev_cls(ofp_event.EventOFPBarrierReply, MAIN_DISPATCHER)
    def barrier_reply_handler(self, ev):
        msg = ev.msg
        print(msg)
        datapath = msg.datapath
        print("barrier_reply_handler ok",datapath.id)
        GLOBAL_VALUE.barrier_lock[datapath.id].release()

    def wait_finish_switch_BARRIER_finish(self,datapath):
        """需要BARRIER但是openvswitch有可能呼叫了但不回傳 導致拖慢設定過程"""
        """print("wait_finish_switch_BARRIER_finish",datapath.id)
        return"""
        print(GLOBAL_VALUE.barrier_lock[datapath.id].counter,"GLOBAL_VALUE.barrier_lock[datapath.id].counter")
        GLOBAL_VALUE.barrier_lock[datapath.id].acquire()
        print(GLOBAL_VALUE.barrier_lock[datapath.id].counter)
        while GLOBAL_VALUE.barrier_lock[datapath.id].counter==0:
            print("barrier_lock",datapath.id)
            self.send_barrier_request(datapath)
            print("send send_barrier_request")
            print(GLOBAL_VALUE.barrier_lock[datapath.id].counter)
            time.sleep(0)
        print("wait_finish_switch_BARRIER_finish ok",datapath.id)
        #print("wait_finish_switch_BARRIER_finish",datapath,"ok")


    def greddy_dynamic(self):
        #貪婪主動動態策略
        while True:  
            GLOBAL_VALUE.route_control_sem.acquire()
            for dst, v in list(GLOBAL_VALUE.PATH.items()):
                dst_datapath_id = GLOBAL_VALUE.ip_get_datapathid_port[dst]["datapath_id"]
                dst_port = GLOBAL_VALUE.ip_get_datapathid_port[dst]["port"]
                for priority,v in list(GLOBAL_VALUE.PATH[dst].items()):
                    src_datapath_id_set=set()
                    #確認有沒有路徑需要被主動模塊優化
                    if len(GLOBAL_VALUE.PATH[dst][priority]["path"])!=0:
                        for path in GLOBAL_VALUE.PATH[dst][priority]["path"]:
                            src_datapath_id_set.add(path[0])
                    else:
                        #沒有要優化就跳過
                        continue
                    all_route_path_list=[]
                    #TODO 這個需要改寫
                    tos=(priority-1)*2
                    for src_datapath_id in src_datapath_id_set:
                        # 拿出目的地port number
                        route_path_list_go,path_length=path_select.k_shortest_path_loop_free_version(self,GLOBAL_VALUE.MAX_K_SELECT_PATH,src_datapath_id[0],src_datapath_id[1],dst_datapath_id,dst_port,weight=str(tos))
                        for idx,i in enumerate(route_path_list_go):
                            all_route_path_list.append(route_path_list_go[idx])  
                    #weight_list_go = [1 for _ in range(len(all_route_path_list))]
                    weight_list_go=path_length
                    print("------動態資訊-----------")
                    print("動態",dst)
                    print("tos",tos)
                    print("src_datapath_id_set",src_datapath_id_set)
                    print(all_route_path_list)
                    self.Setting_Multi_Route_Path(all_route_path_list, weight_list_go, dst,tos=tos,idle_timeout=GLOBAL_VALUE.FLOW_ENTRY_IDLE_TIMEOUT)
                    print("-----------------")
            print("結束主動設定")
            GLOBAL_VALUE.route_control_sem.release()
            hub.sleep(0)
            #time.sleep(0.5)
           

    def active_route(self):
        if GLOBAL_VALUE.active_route_run==False:
            print("主動模塊不啟動")
            return

        hub.sleep(10)
        print("主動模塊啟動")
        if GLOBAL_VALUE.active_greddy_in_active_route:
            print("貪婪主動模塊啟動")
            self.greddy_dynamic()
        #print(nx.adjacency_matrix(GLOBAL_VALUE.G))

        while True:
            if GLOBAL_VALUE.NEED_ACTIVE_ROUTE==False:
                hub.sleep(0.5)
                #print("nono setting")
                continue
            GLOBAL_VALUE.route_control_sem.acquire()
            print("開始主動設定")
            for dst, v in list(GLOBAL_VALUE.PATH.items()):
                dst_datapath_id = GLOBAL_VALUE.ip_get_datapathid_port[dst]["datapath_id"]
                dst_port = GLOBAL_VALUE.ip_get_datapathid_port[dst]["port"]
                for priority,v in list(GLOBAL_VALUE.PATH[dst].items()):
                    src_datapath_id_set=set()
                    #確認有沒有路徑需要被主動模塊優化
                    if len(GLOBAL_VALUE.PATH[dst][priority]["path"])!=0:
                        for path in GLOBAL_VALUE.PATH[dst][priority]["path"]:
                            src_datapath_id_set.add(path[0])
                    else:
                        #沒有要優化就跳過
                        continue

                    all_route_path_list=[]

                    #TODO 這個需要改寫
                    tos=(priority-1)*2
                    
                    for src_datapath_id in src_datapath_id_set:
                        # 拿出目的地port number
                        route_path_list_go,path_length=path_select.k_shortest_path_loop_free_version(self,GLOBAL_VALUE.MAX_K_SELECT_PATH,src_datapath_id[0],src_datapath_id[1],dst_datapath_id,dst_port,weight="ppinin")
                        for idx,i in enumerate(route_path_list_go):
                            all_route_path_list.append(route_path_list_go[idx])
                    
                    #weight_list_go = [1 for _ in range(len(all_route_path_list))]
                    weight_list_go=path_length

                    
                     

                    print("------動態資訊-----------")
                    print("動態",dst)
                    print("tos",tos)
                    print("src_datapath_id_set",src_datapath_id_set)
                    print(all_route_path_list)
                    
                    self.Setting_Multi_Route_Path(all_route_path_list, weight_list_go, dst,tos=tos,idle_timeout=GLOBAL_VALUE.FLOW_ENTRY_IDLE_TIMEOUT)
                    print("-----------------")
            print("結束主動設定")
            GLOBAL_VALUE.route_control_sem.release()
            GLOBAL_VALUE.NEED_ACTIVE_ROUTE=False

            "FIXME 這裡需要加寫當主動設定不好需要退回原本策略"
            #這個設定的時間要大於idle timeout
             
            #print("動態gogo")
      
    
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
        _cookie = GLOBAL_VALUE.get_cookie()
        vlan_tag=1
        for path in route_path_list:
            vlan_tci=ofproto_v1_5.OFPVID_PRESENT+vlan_tag#spec openflow1.5.1 p.82,你要多加這個openvswitch才知道你要設定vlan_vid
            #path:[(1, 4), (1, None), (1, 2), (3, 1), (3, None), (3, 2), (4, 2), (4, None), (4, 3)]
            for index,i in enumerate(path[5::3]):
                set_datapath_id = i[0]
                set_out_port = i[1]
                tmp_datapath = GLOBAL_VALUE.G.nodes[(set_datapath_id, None)]["datapath"]
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
                    OFPT_FLOW_MOD.send_ADD_FlowMod(mod)
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
                    OFPT_FLOW_MOD.send_ADD_FlowMod(mod)
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
            tmp_datapath = GLOBAL_VALUE.G.nodes[(set_datapath_id, None)]["datapath"]
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
        OFPT_FLOW_MOD.send_ADD_FlowMod(mod)
        #上面都完成就紀錄
         
        GLOBAL_VALUE.PATH[ipv4_src][ipv4_dst]["cookie"][_cookie] = route_path_list
        #GLOBAL_VALUE.PATH[ipv4_src][ipv4_dst]["proitity"][priority] = _cookie

 
#test
def Get_NOW_GRAPH(self,dst,priority):
    check_G = nx.DiGraph()
    if GLOBAL_VALUE.PATH[dst][priority]["path"]!={}:
        for path,weight in zip(GLOBAL_VALUE.PATH[dst][priority]["path"],GLOBAL_VALUE.PATH[dst][priority]["weight"]):
            prev_node=None
            for node in path:  
                if prev_node!=None:
                    check_G.add_edge(prev_node, node, weight=1)
                prev_node=node 
    return check_G

 