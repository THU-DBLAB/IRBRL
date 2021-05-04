from mininet.topo import Topo
class MyTopo(Topo):
    def __init__( self ):
        "Create custom topo."

        # Initialize topology
        Topo.__init__(self)
 
        s1 = self.addSwitch('s1',protocols='OpenFlow15')
        s2 = self.addSwitch('s2',protocols='OpenFlow15')
        s3 = self.addSwitch('s3',protocols='OpenFlow15')
        s4 = self.addSwitch('s4',protocols='OpenFlow15')
    
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        h3 = self.addHost('h3')
        h4 = self.addHost('h4')

    
        self.addLink(s1, s2)
        self.addLink(s1, s3)
        self.addLink(s1, s4)
        self.addLink(s4, s3)
        self.addLink(s3, s2)
        self.addLink(h1, s1)
        self.addLink(s4, h2)
        self.addLink(s3, h3)

        self.addLink(h4, s2)

     
    


topos = { 'mytopo': ( lambda: MyTopo() ) }


