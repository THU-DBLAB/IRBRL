from ovs_vsctl import VSCtl
import time
vsctl = VSCtl('tcp', '127.0.0.1', 6641)

def close_port(datapath_id,port_id):
    try:
        popen = vsctl.run('del-port s'+str(datapath_id)+' s'+str(datapath_id)+'-eth'+str(port_id))
        return popen
    except:
        return False

def start_port(datapath_id,port_id):
    try:
        popen = vsctl.run('add-port s'+str(datapath_id)+' s'+str(datapath_id)+'-eth'+str(port_id)+' -- set Interface s'+str(datapath_id)+'-eth'+str(port_id)+' ofport_request='+str(port_id))
        return popen
    except:
        return False

close_port(1,1)

time.sleep(10)
start_port(1,1) 