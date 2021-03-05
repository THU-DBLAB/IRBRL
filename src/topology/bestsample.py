#!/usr/bin/python

from mininet.net import Mininet
from mininet.node import Controller, RemoteController, OVSController
from mininet.node import CPULimitedHost, Host, Node
from mininet.node import OVSKernelSwitch, UserSwitch
from mininet.node import IVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink, Intf
from subprocess import call


def myNetwork():

    net = Mininet(topo=None,
                  build=False,
                  ipBase='10.0.0.0/8')

    info('*** Adding controller\n')
    c0 = net.addController(name='c0',
                           controller=Controller,
                           protocol='tcp',
                           port=6633)

    info('*** Add switches\n')
    #s2 = net.addSwitch('s2', cls=OVSKernelSwitch,protocols='OpenFlow15',ip="10.0.0.3")
    s1 = net.addSwitch('s1', cls=OVSKernelSwitch,protocols='OpenFlow15',ip="10.0.0.4")
     
    #s2.cmd('sudo ethtool -s s2-eth1 speed 100')
    info('*** Add hosts\n')
    h1 = net.addHost('h1', cls=Host, ip='10.0.0.1', defaultRoute="via 140.128.102.174")
    h2 = net.addHost('h2', cls=Host, ip='10.0.0.2', defaultRoute=None)
    meter=0*1000
    delay="100ms"
    info('*** Add links\n')
    #https://github.com/mininet/mininet/blob/de28f67a97fc8915cc1586c984465d89a016d8eb/mininet/link.py#L314
    net.addLink(s1, h1,cls=TCLink, bw=1000,jitter="0ms",delay="10ms",loss=0,max_queue_size=10000000)
    net.addLink(h2, s1,cls=TCLink, bw=1000,jitter="0ms",delay="10ms",loss=0,max_queue_size=10000000)
    #mininet 的delay,jitter,loss底層是依靠netem(Network Emulation)模擬
    #由於mininet底層呼叫netem時沒有設定jitter的分佈狀態,所以netem依照默認設定是normal(常態分佈)
    #https://git.kernel.org/pub/scm/network/iproute2/iproute2.git/tree/man/man8/tc-netem.8#n89
     
    #在netem指令之下jitter可以設定三種
    #https://git.kernel.org/pub/scm/network/iproute2/iproute2.git/tree/man/man8/tc-netem.8#n23
    #uniform " | " normal " | " pareto " |  " paretonormal
 
    #net.addLink(s1, s2,port1=888,port2=321,cls=TCLink, bw=1000,jitter="450ms",delay="0.75s",loss=11,max_queue_size=23)
    #print(str(l),"****jjjjjjjjjjjjjjjjjj****")
    #net.addLink(s1, s2,port1=433,port2=32232,cls=TCLink, bw=10,jitter="0ms",delay="0s",loss=0,max_queue_size=2223)

    #print(a)
    #a.cmd("sudo ethtool -s s1-eth1 speed 100")
    #a.cmd("sudo ethtool -s s2-eth1 speed 100")
    
   
    info('*** Starting network\n')
    net.build()
    ##
    #print(s1.cmd('sudo ethtool -s s1-eth888 speed 1000'))
    #s1.cmd('sudo ethtool -s s1-eth433 speed 10')
    #s1.cmd('sudo ethtool -s s2-eth321 speed 1000')
    #s1.cmd('sudo ethtool -s s2-eth32232 speed 10')
    #s2.cmd('sudo ethtool -s s2-eth32232 speed 1000')
    
    #print(s1.cmd('sudo ethtool -s s2-eth1 speed 1000000'))
    ##
    info('*** Starting controllers\n')
    for controller in net.controllers:
        controller.start()

    info('*** Starting switches\n')
    #net.get('s2').start([c0])
    net.get('s1').start([c0])

    info('*** Post configure switches and hosts\n')
    #net.pingAll(0.1)
     
    CLI(net)
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    myNetwork()
