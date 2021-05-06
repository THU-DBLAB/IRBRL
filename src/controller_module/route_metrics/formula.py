#python

#Reference:D. Teare, Implementing Cisco IP Routing (ROUTE) Foundation Learning Guide: Foundation learning for the ROUTE 642-902 Exam (Self-Study Guide), 1st ed. Cisco Press, 2010.
"""
This formula can also be written as (108) / (bandwidth in bps). Note The OSPF RFC 2328 does not specify what the link cost should be, but on Cisco routers it defaults to being inversely proportional to the link’s bandwidth
"""

def OSPF(bps):
    return 10**8/bps

#D. Savage, J. Ng, S. Moore, D. Slice, P. Paluch, and R. White, “Cisco’s Enhanced Interior Gateway Routing Protocol (EIGRP),” no. 7868. RFC Editor, 2016.[Page 42] 
"""
K1 == K3 == 1
K2 == K4 == K5 == 0
K6 == 0
"""
def EIGRP(bw_kbps,curr_speed,tx_bytes_delta,DELAY,loss,K1=1,K2=0,K3=1,K4=0,K5=0):
    BW=10**7/bw_kbps
    REL=round((1-loss)*255,0)
    LOAD=round((tx_bytes_delta/(curr_speed*1000/8))*255,0)
    metric=256*(  ( (K1*BW) + ( (K2*BW)/(256-LOAD) ) + (K3*DELAY) ) * (K5/(REL+K4)) )
    return metric