import networkx as nx
import matplotlib.pyplot as plt

G=nx.Graph()

G.add_node(1)

G.add_node(2)
 
G.add_node(4)
 
G.add_edge(1,2)
G.add_edge(1,2)
G.add_edge(2,1) 
G.edges[1,2]["ss"]=2
print(G.edges[1,2],G.edges[2,1])
#nx.draw(G)
#plt.show()
