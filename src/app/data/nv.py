#python
import networkx as nx
import itertools
import copy
import networkx as nx
import pandas as pd
import matplotlib.pyplot as plt
G=nx.Graph()
G.add_edges_from([(1,2),(1,3),(1,4),(3,4)])
 
G.nodes(data=True)

G.node[1]['attribute']='value'
G.nodes(data=True)
plt.figure(figsize=(8, 6))
nx.draw(G )

plt.title('Graph Representation of Sleeping Giant Trail Map', size=15)
 
plt.show()
