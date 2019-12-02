#python
def eth_1105_decode(dst_mac,src_mac):
    datapath_id_mac=dst_mac+":"+src_mac[0:5]
    port_no=src_mac[6:]
    return int(datapath_id_mac.replace(":", ""),16),int(port_no.replace(":", ""),16 )
 
def eth_1105_encode(datapath_id,out_port):
    def hex_to_mac(mac_hex):
        return ":".join(mac_hex[i:i+2] for i in range(0, len(mac_hex), 2))
    dst_hex = "{:016x}".format(datapath_id)[0:12]
        
    src_hex = "{:016x}".format(datapath_id)[12:]+"{:08x}".format(out_port)
    return hex_to_mac(dst_hex),hex_to_mac(src_hex)

dst,src=eth_1105_encode(88888888,55555543)  
print(dst,src)
print(eth_1105_decode(dst,src))