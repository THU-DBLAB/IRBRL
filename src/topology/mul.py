from mininet.topo import Topo

class MyTopo( Topo ):
    "Simple topology example."

    def __init__( self ):
        "Create custom topo."

        # Initialize topology
        Topo.__init__( self )

        # Add hosts and switches
        h1 = self.addHost( 'h1' )
        h2 = self.addHost( 'h2' )

        s3 = self.addSwitch( 's3' )
        s4 = self.addSwitch( 's4' )
        


        s5 = self.addSwitch( 's5' )
        s6 = self.addSwitch( 's6' )
        s7 = self.addSwitch( 's7' )

        # Add links
        self.addLink( h1, s3 )
        self.addLink( h2, s4 )

        self.addLink( s5, s3 )
        self.addLink( s5, s4 )
        
        self.addLink( s6, s3 )
        self.addLink( s6, s4 )

        self.addLink( s7, s3 )
        self.addLink( s7, s4 )

topos = { 'mytopo': ( lambda: MyTopo() ) }
