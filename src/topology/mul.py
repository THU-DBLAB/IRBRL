from mininet.topo import Topo

class MyTopo( Topo ):
    "Simple topology example."

    def __init__( self ):
        "Create custom topo."

        # Initialize topology
        Topo.__init__(self)

        # Add hosts and switches
        h1 = self.addHost( 'h1' )
        h2 = self.addHost( 'h2' )

        s3 = self.addSwitch( 's3' )
        s4 = self.addSwitch( 's4' )
        self.addLink( h1, s3 )
        self.addLink( h2, s4 )


        for i in range(5,14):

            s5 = self.addSwitch( 's5'+str(i) )
        
            self.addLink( s5, s3 )
            self.addLink( s5, s4 )
topos = { 'mytopo': ( lambda: MyTopo() ) }
