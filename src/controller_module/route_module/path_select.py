from controller_module import GLOBAL_VALUE
from networkx.classes.function import path_weight
import networkx as nx
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
        shortest_simple_paths=nx.shortest_simple_paths(GLOBAL_VALUE.G, (src_datapath_id, src_port), (dst_datapath_id, dst_port), weight=weight)
    except:
        return
    for path in shortest_simple_paths:
        if len(loop_free_path)==k:
            break
        prev_node=None
        for node in path:  
            if prev_node!=None:
                 
                loop_check.add_edge(prev_node, node, weight=GLOBAL_VALUE.G[prev_node][node][weight])
            prev_node=node 
        _check_free=loop_check.check_free_loop()
        if _check_free:
            loop_free_path.append(path)
            path_length.append(path_weight(GLOBAL_VALUE.G, path, weight=weight))
    
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
    for idx,path in enumerate(nx.shortest_simple_paths(GLOBAL_VALUE.G, (src_datapath_id, src_port), (dst_datapath_id, dst_port), weight=weight)):
        if idx==0:
            best_length=path_weight(GLOBAL_VALUE.G, path, weight=weight)
            ok_path.append(path)
            continue
        if best_length==path_weight(GLOBAL_VALUE.G, path, weight=weight):
            ok_path.append(path)
        else:
            break      
    return ok_path,best_length


def k_shortest_path_first_and_maximum_flow_version(self,k,src_datapath_id,src_port,dst_datapath_id,dst_port,check_G=None,weight="weight"):
    #這個保證路徑沒有loop
    #當我們想要考量 最大剩餘頻寬 於鏈路cost如何合併? 
    loop_free_path=[]
    path_length=[]
    loop_check=Loop_Free_Check(check_G)
    for path in nx.shortest_simple_paths(GLOBAL_VALUE.G, (src_datapath_id, src_port), (dst_datapath_id, dst_port), weight=weight):
        if len(loop_free_path)==k:
            break
        prev_node=None
        for node in path:  
            if prev_node!=None:
                print(prev_node,node,weight)
                loop_check.add_edge(prev_node, node, weight=GLOBAL_VALUE.G[prev_node][node][weight])
            prev_node=node 
        _check_free=loop_check.check_free_loop()
        if _check_free:
            loop_free_path.append(path)
            path_length.append(path_weight(GLOBAL_VALUE.G, path, weight=weight))

     
    return loop_free_path,path_length


def k_maximum_flow_loop_free_version(self,k,src_datapath_id,src_port,dst_datapath_id,dst_port,check_G=None,weight="weight",capacity="capacity"):
    #這個保證路徑沒有loop
    #當我們想要考量 最大剩餘頻寬 於鏈路cost如何合併? 
    loop_free_path=[]
    path_length=[]
    tmp_G=GLOBAL_VALUE.G.copy()

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
    for path in nx.shortest_simple_paths(GLOBAL_VALUE.G, (src_datapath_id, src_port), (dst_datapath_id, dst_port), weight=weight):
        tmp_check_G=check_G.copy()
        if len(loop_free_path)==k:
            break
        prev_node=None
        for node in path:  
            if prev_node!=None:
                tmp_check_G.add_edge(prev_node, node, weight=GLOBAL_VALUE.G[prev_node][node][weight])
            prev_node=node 
        try:
            nx.find_cycle(tmp_check_G, orientation="original")
        except:
            check_G=tmp_check_G
            loop_free_path.append(path)
            path_length.append(path_weight(check_G, path, weight=weight))
    return loop_free_path,path_length


 

 