#Author:LU-YI-HSUN 
#Algotherm:Recurrence Plots
#http://www.recurrence-plot.tk/glance.php

import numpy as np
import pylab as plt
import sklearn as sk
#Algotherm Author:J.-P Eckmann and S. Oliffson Kamphorst and D Ruelle
#https://en.wikipedia.org/wiki/Recurrence_plot
def vanilla_rec_plot(s, eps=None):
    """
    s[data.len][data.dimension]
    """
    if eps==None: eps=20
    N = s.shape[0]
    S = np.repeat(s[None,:], N, axis=0)
    S_T=np.transpose(S,(1,0,2))#https://stackoverflow.com/questions/32034237/how-does-numpys-transpose-method-permute-the-axes-of-an-array
    Z=eps-np.linalg.norm(S-S_T,axis=(2))
    Z[Z>0]=1
    Z[Z<=0]=0
    return Z

#Algotherm Author:dawid
#https://laszukdawid.com/about/
#https://laszukdawid.com/2015/09/04/emd-on-audio-wav-and-recurrance-plots/
def rec_plot(s, eps=None,steps=None):
    """
    s[data.len][data.dimension]
    """
    if eps==None: eps=0.01
    if steps==None: steps=10
    N = s.shape[0]
    S = np.repeat(s[None,:], N, axis=0)
    S_T=np.transpose(S,(1,0,2))#https://stackoverflow.com/questions/32034237/how-does-numpys-transpose-method-permute-the-axes-of-an-array
    Z=eps-np.linalg.norm(np.floor(S-S_T)/eps,axis=(2))
    Z[Z>steps] = steps
    return Z

def recurrence_plot(s, eps=None, steps=None):
    if eps==None: eps=0.1
    if steps==None: steps=10
    d = sk.metrics.pairwise.pairwise_distances(s)
    d = np.floor(d / eps)
    d[d > steps] = steps
    #Z = squareform(d)
    return d
if __name__ == "__main__":
    x = np.floor(np.random.rand(665,15)*10)+10
    sig = x
    #vanilla vers.
    print("vanilla")
    rec=vanilla_rec_plot(sig)
    plt.imshow(rec)
    plt.show()
    #dawid vers.
    print("dawid")
    rec = rec_plot(sig)
    plt.imshow(rec)
    plt.show()

    recurrence_plot(sig)
    plt.imshow(rec)
    plt.show()