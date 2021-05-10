from ryu.ofproto import ofproto_v1_5
from controller_module import GLOBAL_VALUE
from ryu.lib.packet import ethernet, arp, icmp, ipv4
def send_add_group_mod(datapath, port_list: list, weight_list: list,vlan_tag_list:list, group_id: int):
        """
        group_id是給flow entry指引要導到哪個group entry
        """
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser
        buckets = []
        # Each bucket of the group must have an unique Bucket ID-openflow1.51-p115 所以亂給個id給它 反正我沒用到
        bucket_id = 0
        for port, weight,vlan_vid in zip(port_list, weight_list,vlan_tag_list):
            #bucket_id=GLOBAL_VALUE.G.nodes[(datapath.id,None)]["now_max_group_id"]
            assert 1<=vlan_vid<=4095,"vlan_vid range need in 1~4095"#vlan_vid 1~4095
            
            vlan_tci=ofproto_v1_5.OFPVID_PRESENT+vlan_vid#spec openflow1.5.1 p.82,你要多加這個openvswitch才知道你要設定vlan_vid
            """
            enum ofp_vlan_id { 
                OFPVID_PRESENT = 0x1000, /* Bit that indicate that a VLAN id is set */ 
                OFPVID_NONE = 0x0000, /* No VLAN id was set. */
            };
            """
            #三個動作1.Push VLAN header" 2."Set-Field VLAN_VID value"3."Output port" 
            actions = [ofp_parser.OFPActionPushVlan(ether_types.ETH_TYPE_8021Q),ofp_parser.OFPActionSetField(vlan_vid=vlan_tci),ofp_parser.OFPActionOutput(port)]
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
            GLOBAL_VALUE.G.nodes[(datapath.id, None)]["now_max_group_id"] = GLOBAL_VALUE.G.nodes[(
                datapath.id, None)]["now_max_group_id"]+1
        # 從多個路線根據權重(weight)隨機從buckets選一個OFPBucket(ofp.OFPGT_SELECT),OFPBucket裡面就放要actions要出去哪個port
        mod = ofp_parser.OFPGroupMod(datapath, command=ofp.OFPGC_ADD,
                                     type_=ofp.OFPGT_SELECT, group_id=group_id, buckets=buckets)
        mod.xid = GLOBAL_VALUE.G.nodes[(datapath.id, None)]["now_max_xid"]
        #print(mod.xid,mod)
        GLOBAL_VALUE.G.nodes[(datapath.id, None)]["now_max_xid"] = GLOBAL_VALUE.G.nodes[(
            datapath.id, None)]["now_max_xid"]+1
        datapath.send_msg(mod)

def send_add_group_mod_v1(datapath,port_list:list,weight_list:list,group_id:int):
     
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
        #bucket_id=GLOBAL_VALUE.G.nodes[(datapath.id,None)]["now_max_group_id"]
        actions = [ofp_parser.OFPActionOutput(port)]
        #spec openflow1.5.1 p.116  struct ofp_group_bucket_prop_weight
        #注意ryu ofv1.5.1的group範例寫錯
        #下面這個寫法要靠自己挖ryu原始碼才寫出來,所以遇到問題盡量挖控制器ryu,openvswitch原始碼
        #ofp_bucket->properties->ofp_group_bucket_prop_weight-spec openflow1.5.1 p.115~p.116 
        _weight=ofp_parser.OFPGroupBucketPropWeight(weight=weight,length=8,type_=ofp.OFPGBPT_WEIGHT)
        buckets.append(ofp_parser.OFPBucket(bucket_id=bucket_id,actions=actions,properties=[_weight]))
        bucket_id=bucket_id+1
    
    #GLOBAL_VALUE.G.nodes[(datapath.id,None)]["now_max_group_id"]=GLOBAL_VALUE.G.nodes[(datapath.id,None)]["now_max_group_id"]+1
    #從多個路線根據權重(weight)隨機從buckets選一個OFPBucket(ofp.OFPGT_SELECT),OFPBucket裡面就放要actions要出去哪個port
     
    command=None
    if GLOBAL_VALUE.G.nodes[(datapath.id,None)]["GROUP_TABLE"][group_id]=={}:
        command=ofp.OFPGC_ADD
    else:
        command=ofp.OFPGC_MODIFY

    mod = ofp_parser.OFPGroupMod(datapath, command=command,type_=ofp.OFPGT_SELECT, group_id=group_id, buckets=buckets)
    mod.xid=GLOBAL_VALUE.get_xid(datapath.id)
    datapath.send_msg(mod)
    GLOBAL_VALUE.G.nodes[(datapath.id,None)]["GROUP_TABLE"][group_id]=mod

    GLOBAL_VALUE.error_search_by_xid[datapath.id][mod.xid]=mod
