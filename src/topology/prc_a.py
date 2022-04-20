#計算ping處理aa 低延遲占比
from itertools import count
import matplotlib.pyplot as plt
import seaborn as sns
sns.set_theme(style="whitegrid")
f=open("test","r")
 
ok=f.read()

mini_delay=0
all_count=0
c=300
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
            print(mini_delay/c)
            all_.append(mini_delay/c)
            all_x.append(all_data)
            mini_delay=0
            ans.append(tmp_ans)
            tmp_ans=[]

 

ax=sns.lineplot(x=all_x,y=all_) 
print(ax)
print(all_data)
ax.set(xlabel='each '+str(c)+" ping data("+str(all_data)+")", ylabel='Probability Of Find minimum Delay Path', title="greedy PPO")
plt.savefig('data.png')
#plt.show()

#0 10 20 30 40 thousanl