from ryu.ofproto import ofproto_v1_5
from controller_module import GLOBAL_VALUE
from ryu.lib.packet import ethernet, arp, icmp, ipv4
from sklearn.preprocessing import minmax_scale
from ryu.lib import pack_utils

#這裡探討如何設定select的hash
#https://github.com/openvswitch/ovs/blob/master/Documentation/group-selection-method-property.txt

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
        

       

def send_add_group_mod_v1(datapath,port_list:list,weight_list:list,group_id:int,dry_run=False):
    #ofp_group_bucket_prop_weight 的weight為uint16_t所以0~65535
    #沒必要設定權重0所以要把數值壓縮在1~65535
    #注意型態weight_list [np.int64,np.int64...]
    print("send_add_group_mod_v1")
    weight_list=list(minmax_scale(weight_list,feature_range=(1,65535)).astype(int))
  
    
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

        _weight=ofp_parser.OFPGroupBucketPropWeight(weight=int(weight),length=8,type_=ofp.OFPGBPT_WEIGHT)
         
        buckets.append(ofp_parser.OFPBucket(bucket_id=bucket_id,actions=actions,properties=[_weight]))
        bucket_id=bucket_id+1
    
    #GLOBAL_VALUE.G.nodes[(datapath.id,None)]["now_max_group_id"]=GLOBAL_VALUE.G.nodes[(datapath.id,None)]["now_max_group_id"]+1
    #從多個路線根據權重(weight)隨機從buckets選一個OFPBucket(ofp.OFPGT_SELECT),OFPBucket裡面就放要actions要出去哪個port
     
    command=None
    if GLOBAL_VALUE.G.nodes[(datapath.id,None)]["GROUP_TABLE"][group_id]=={}:
        command=ofp.OFPGC_ADD
    else:
        command=ofp.OFPGC_MODIFY
    #openvswitch擴展協議可以控制group table 的hash的演算法
    #https://github.com/openvswitch/ovs/blob/master/Documentation/group-selection-method-property.txt
    #底下黑魔法寫法 ryu的OFPGroupBucketPropExperimenter結構不適合寫我硬繞過去所以醜醜
    
   
     
    properties=[]
    #目前還不可用
    """
    hash_alog="nohash"
    hash_alog="hash"

    if hash_alog=="hash":
        #"hash" ascii == 0x68617368 
        
        hash_alog_magic=[0,     0x68617368,0,0,0,                   0,0,                      0xFFFF0008]
                        #pad,   selection_method[1:4]           selection_method_param      OXM header      OFPXMC_EXPERIMENTER(FFFF)
        _select_method=ofp_parser.OFPGroupBucketPropExperimenter(type_=ofp.OFPGBPT_EXPERIMENTER,exp_type=1,experimenter=0x0000154d,data=hash_alog_magic)
        
        properties=[_select_method]
    """

    mod = ofp_parser.OFPGroupMod(datapath, command=command,type_=ofp.OFPGT_SELECT, group_id=group_id, buckets=buckets,properties=properties)
    if dry_run:
        return mod
    #xid為了讓控制器知道哪個動作是錯誤的
    mod.xid=GLOBAL_VALUE.get_xid(datapath.id)
    print("send_add_group_mod_v1acquire")
    
    datapath.send_msg(mod)
    
    print("send_add_group_mod_v1release")

     

    GLOBAL_VALUE.G.nodes[(datapath.id,None)]["GROUP_TABLE"][group_id]=mod
    #當發生錯誤就可以搜尋哪個動錯出錯
    GLOBAL_VALUE.error_search_by_xid[datapath.id][mod.xid]=mod
    return mod

