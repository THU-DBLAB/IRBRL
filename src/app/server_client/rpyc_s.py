#python
import rpyc
import sys
c = rpyc.classic.connect("localhost")
c.execute("print('hi python cookbook')")
c.modules.sys.stdout = sys.stdout
c.execute("print('hi here')")