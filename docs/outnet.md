# mininet的host該如何連線外網

## Step 0 關閉防火牆

確認防火牆是否啟動,就是因為啟動防火牆我的veth無法傳出DNS協定

```
sudo firewall-cmd --state
```

先暫時關閉

```
sudo systemctl stop firewalld
```


## Step1 啟動mn

先啟動mininet 並且用default的拓樸當範例
```
sudo mn
```

## Step2 找host 1的PID

 
ref:http://www.haifux.org/lectures/299/netLec7.pdf


由於mininet 是設定Nameless namespaces所以```ip netns list``` 是看不到namespaces因為mininet沒有命名
所以我們要先找出"Nameless namespaces" 的PID

執行完成底下的python2程式可以看到跟我類似的輸出,可以看到mininet設定h1的PID為9051,先記下該PID等等會幫該Nameless namespaces命名
 
```
      9051  net:[4026532791]      bash --norc --noediting -is mininet:h1 
      9051  mnt:[4026532789]      bash --norc --noediting -is mininet:h1 
      9053  net:[4026532853]      bash --norc --noediting -is mininet:h2 
      9053  mnt:[4026532851]      bash --norc --noediting -is mininet:h2
```
 
 


ref:https://www.opencloudblog.com/?p=251

該作者程式是python2我改為相容python2與3版本

執行要加sudo
```python
#!/usr/bin/python
#
# List all Namespaces (works for Ubuntu 12.04 and higher)
#
# (C) Ralf Trezeciak    2013-2014
#
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
import os
import fnmatch

if os.geteuid() != 0:
    print ("This script must be run as root\nBye")
    exit(1)

def getinode( pid , type):
    link = '/proc/' + pid + '/ns/' + type
    ret = ''
    try:
        ret = os.readlink( link )
    except OSError as e:
        ret = ''
        pass
    return ret

#
# get the running command
def getcmd( p ):
    try:
        cmd = open(os.path.join('/proc', p, 'cmdline'), 'rb').read()
        if cmd == '':
            cmd = open(os.path.join('/proc', p, 'comm'), 'rb').read()
        cmd=str(cmd)
        cmd = cmd.replace("\\x00" , ' ')
        cmd = cmd.replace("b'" , ' ')
        cmd = cmd.replace("'" , ' ')
        cmd = cmd.replace('\n' , ' ')
        return cmd
    except:
        return ""
    
#
# look for docker parents
def getpcmd( p ):
    try:
        f = '/proc/' + p + '/stat'
        arr = open( f, 'rb').read().split()
        cmd = getcmd( arr[3] )
        if cmd.startswith( '/usr/bin/docker' ):
            return 'docker'
    except:
        pass
    return ''
#
# get the namespaces of PID=1
# assumption: these are the namespaces supported by the system
#
nslist = os.listdir('/proc/1/ns/')
if len(nslist) == 0:
    print ('No Namespaces found for PID=1')
    exit(1)
#print nslist
#
# get the inodes used for PID=1
#
baseinode = []
for x in nslist:
    baseinode.append( getinode( '1' , x ) )
#print "Default namespaces: " , baseinode
err = 0
ns = []
ipnlist = []
#
# loop over the network namespaces created using "ip"
#
try:
    netns = os.listdir('/var/run/netns/')
    for p in netns:
        fd = os.open( '/var/run/netns/' + p, os.O_RDONLY )
        info = os.fstat(fd)
        os.close( fd)
        ns.append( '-- net:[' + str(info.st_ino) + '] created by ip netns add ' + p )
        ipnlist.append( 'net:[' + str(info.st_ino) + ']' )
except:
    # might fail if no network namespaces are existing
    pass
#
# walk through all pids and list diffs
#
pidlist = fnmatch.filter(os.listdir('/proc/'), '[0123456789]*')
#print pidlist
for p in pidlist:
    try:
        pnslist = os.listdir('/proc/' + p + '/ns/')
        for x in pnslist:
            i = getinode ( p , x )
            if i != '' and i not in baseinode:
                cmd = getcmd( p )
                pcmd = getpcmd( p )
                if pcmd != '':
                    cmd = '[' + pcmd + '] ' + cmd
                tag = ''
                if i in ipnlist:
                    tag='**' 
                ns.append( p + ' ' + i + tag + ' ' + cmd)
                
    except:
        # might happen if a pid is destroyed during list processing
        pass
#
# print the stuff
#
print ('{0:>10}  {1:20}  {2}'.format('PID','Namespace','Thread/Command'))
for e in ns:
    x = e.split( ' ' , 2 )
    print ('{0:>10}  {1:20}  {2}'.format(x[0],x[1],x[2][:60]))
 
```

 
## Step 3 namespaces命名

ref:https://gist.github.com/cfra/39f4110366fa1ae9b1bddd1b47f586a3

還記得我們PID為9051,現在要幫該Nameless namespaces命名

new_namespace你可以改成自己喜歡的namespaces

本範例h1的namespace都為new_namespace

網卡interface都假定為:wlp3s0

這個9051要改成你看到的PID

你可能在/run/底下沒有netns資料夾所以新增一個
如果已經有了就不用
```
sudo mkdir /run/netns/
```

新增檔案與掛載

```
sudo touch /run/netns/new_namespace
sudo mount -o bind /proc/9051/ns/net /run/netns/new_namespace
```

再來我們測試能不能直接使用namespace直接進入h1

```
sudo ip netns exec new_namespace bash
```

離開h1
```
exit
```

## Step 4 開始設定

### 解法1

有橋接版本

docker就是依靠此方式建立網路隔離

底下教學來源ref: https://www.itread01.com/content/1543209484.html#2veth_pair_8

建立veth pair
```
sudo ip link add veth-1 type veth peer name veth-2
```

把veth-2塞入new_namespace

```
sudo ip link set dev veth-2 netns new_namespace
```


啟動veth-1與veth-2
並且對h1也就是new_namespace做設定
```
sudo ip link set dev veth-1 up
sudo ip netns exec new_namespace ip link set dev veth-2 up
sudo ip netns exec new_namespace ip addr add 10.0.0.1/24 dev veth-2
```

新增虛擬網橋

```
sudo ip link add br0 type bridge
sudo ip link set dev br0 up
sudo ip addr add 10.0.0.254/24 dev br0
```

把veth-1跟br0相連

```
sudo ip link set dev veth-1 master br0
```

在new_namespace名稱空間裡面新增預設路由
```
sudo ip netns exec new_namespace ip route add default via 10.0.0.254 dev veth-2
```

啟動轉發ipv4流量

```
echo 1 > /proc/sys/net/ipv4/ip_forward
```

這邊要注意wlp3s0要改成你可以連外網的interface

新增iptables FORWARD 規則
```
sudo iptables -A FORWARD --out-interface wlp3s0 --in-interface br0 -j ACCEPT
sudo iptables -A FORWARD --in-interface wlp3s0 --out-interface br0 -j ACCEPT
```

新增iptables NAT 規則
```
sudo iptables -t nat -A POSTROUTING --source 10.0.0.0/24 --out-interface wlp3s0 -j MASQUERADE
```

### 懶人解法2

沒有橋接版本

ref:https://gist.github.com/dpino/6c0dca1742093346461e11aa8f608a99

ref2:https://gist.githubusercontent.com/Lu-Yi-Hsun/708155264a436ca3e33551f26ea25630/raw/3b9f0ce358377cb5c2ecb4dd9a954df586adbe94/ns-inet.sh


#### 下載bash檔

```
wget https://gist.githubusercontent.com/Lu-Yi-Hsun/708155264a436ca3e33551f26ea25630/raw/3b9f0ce358377cb5c2ecb4dd9a954df586adbe94/ns-inet.sh
```

#### 設定ns-inet.sh為可執行

```
chmod +x ns-inet.sh
```

 
#### 執行
改成你自己的設定

我上網的網卡是:wlp3s0

我的namespace:new_namespace

!!! note
    注意當使用此bash進入namespace後並且離開mininet的xterm h1設定會恢復如果要讓xterm h1可以持續上網就別離開此指令
```
sudo ./ns-inet.sh wlp3s0 new_namespace
```

#### 測試


```
ping www.google.com
```

在host1執行chrome上網
```
google-chrome-stable --no-sandbox
```