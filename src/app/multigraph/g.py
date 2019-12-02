#python
import networkx as nx
G = nx.MultiGraph()
G.add_node(1)
G.add_node(2)
G.add_edges_from([(1,2,55), (1,2,66)])
print(G[1][2])
 