#計算ping處理aa 低延遲占比
from itertools import count
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
sns.set_theme(style="whitegrid")
c=200
def get_ping(file):
    global c
    f=open(file,"r")
    
    ok=f.read()
    mini_delay=0
    all_count=0
    
    ans=[]
    tmp_ans=[]
    all_=[]
    all_x=[]
    all_data=0
    for i in ok.split("\n"):
        
        i_d=i.split("time=")
        if len(i_d)==2:
            all_data=all_data+1
            minsec=float(i_d[1].replace("ms",""))
            all_count=all_count+1
            tmp_ans.append(minsec)
            
            if float(i_d[1].replace("ms",""))<1:
                mini_delay=mini_delay+1
                
            if all_count%c==0:
                #print(mini_delay/c)
                all_.append(mini_delay/c)
                all_x.append(all_data)
                mini_delay=0
                ans.append(tmp_ans)
                tmp_ans=[]
    return all_x,all_

all_x,all_=get_ping("greedy")
all_x_no,all_no=get_ping("no_greedy")
max_l=min(len(all_x),len(all_x_no))

 
all_data=all_x[-1]
x=[]
x.append(all_x[0:max_l])
x.append(all_x_no[0:max_l])
y=[]
y.append(all_[0:max_l])
y.append(all_no[0:max_l])
 
d_all_ok = []
print(max_l)
for idx,val in enumerate(all_x[0:max_l]):
    d={}
     
    d={"algorithm":'Greedy with PPO'}
    d["x"]=val
    d["y"]=all_[idx]
    d_all_ok.append(d)
for idx,val in enumerate(all_x_no[0:max_l]):
    d={}
     
    d={"algorithm":'PPO'}
    d["x"]=val
    d["y"]=all_no[idx]
    d_all_ok.append(d)
      

print(d_all_ok)
 
df = pd.DataFrame(data=d_all_ok)

ax=sns.lineplot(data=df,x="x",y="y",hue="algorithm" ,markers=True, dashes=False, ci=68) 
print(ax)
print(all_data)

ax.set(xlabel='each '+str(c)+" ping data("+str(all_data)+")", ylabel='Probability Of Find minimum Delay Path', title="")
plt.savefig('data.png')
#plt.show()

#0 10 20 30 40 thousanl