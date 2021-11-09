# 錯誤排解

## Mininet Cannot find required executable controller



if you get this problen
```bash
Cannot find required executable controller.
Please make sure that it is installed and available in your $PATH:
(/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin)
```
### fix
```
sudo apt-get install openvswitch-testcontroller
sudo ln /usr/bin/ovs-testcontroller /usr/bin/controller 
```


source:https://stackoverflow.com/a/47312367

## port衝突

在實驗時都在default設定之下,因為ryu啟動LISTEN的ip為0.0.0.0:6653

但是mininet 連線的位置為127.0.0.1:6653 所以無法連線

!!! bug 
    ```bash
    Please shut down the controller which is running on port 6653
    ```
 

解決方案要確實指定正確ip

!!! fix 
    ```bash
    sudo mn --controller=remote,ip=0.0.0.0,port=6653
    ```

## miniedit版本問題

https://github.com/mininet/mininet/blob/master/examples/miniedit.py

目前miniedit.py只支援python2

## 啟動拓樸卡住

當卡在這裡
!!! bug
    ```bash
    *** Adding controller
    *** Add switches
    *** Add hosts
    *** Add links
    *** Starting network
    *** Configuring hosts
    h2 h1 
    *** Starting controllers
    *** Starting switches
    ```

### 解決方案
有可能是尚未啟動openvswitch

下這個指令
!!! fix
    ```
    sudo ovs-vswitchd
    ```
## OVSDB連線問題

ovsdb-server 的啟動監聽位置要與OVSDB_ADDR 一樣

支援兩個地方控制db.sock與ptcp:6641

for manjaro

```bash
sudo ovsdb-server --remote=punix:/run/openvswitch/db.sock --remote=ptcp:6641 --pidfile=/run/openvswitch/ovsdb-server.pid
```

for ubuntu

```bash
sudo ovsdb-server --remote=punix:/usr/local/var/run/openvswitch/db.sock --remote=ptcp:6641 --pidfile
```

安裝ovs_vsctl

```bash
sudo pip3 install git+https://github.com/iwaseyusuke/python-ovs-vsctl.git
```

```python
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
close_port(33,1)
close_port(33,2)
time.sleep(10)
start_port(33,1)
start_port(33,2)
```


## METER TABLE設定問題

!!! NOTE 
    Open vSwitch有兩種用作模式核心(system)模式與user space(netdev)模式運作此模式需要安裝DPDK與編譯DPDK版本的Open vSwitch

datapath_types [netdev, system]

### 核心(system)
 
Open vSwitch 2.10才開始在核心(system)模式實做meter並且Linux kernel版本要高於4.15才支援meter table

http://docs.openvswitch.org/en/latest/faq/releases/

### user space(netdev)

Open vSwitch 2.7開始在user space(netdev)實做meter,所以要使用必須安裝DPDK
使用DPDK+Open vSwitch可以讓user space(netdev)模式的Open vSwitch提高吞吐量

mininet要設定datapath為user才能使用user space轉發,
```
sudo mn --topo single,2 --switch ovs,protocols=OpenFlow13,datapath=user
```

## 執行時期錯誤

ryu由python撰寫的而線程是單核心,當你的拓樸規模過大會導致ryu的綠線程[eventlet](https://github.com/eventlet/eventlet)優先權或是排擠影響個別模塊功能.需要注意