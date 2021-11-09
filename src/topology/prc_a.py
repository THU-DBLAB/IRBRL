#計算ping處理aa 低延遲占比
import matplotlib.pyplot as plt
import seaborn as sns
sns.set_theme(style="whitegrid")
f=open("myt2","r")
 
ok=f.read()

mini_delay=0
all_count=0
c=5000
ans=[]
tmp_ans=[]
all_=[]
for i in ok.split("\n"):
    
    i_d=i.split("time=")
    if len(i_d)==2:
        minsec=float(i_d[1].replace("ms",""))
        all_count=all_count+1
        tmp_ans.append(minsec)
         
        if float(i_d[1].replace("ms",""))<1:
            mini_delay=mini_delay+1
            
        if all_count%c==0:
            print(mini_delay/c)
            all_.append(mini_delay/c)
            mini_delay=0
            ans.append(tmp_ans)
            tmp_ans=[]

 

ax=sns.lineplot(data=all_) 
ax.set(xlabel='each '+str(c)+" ping data", ylabel='Probability', title='Probability Of Find minimum Delay Path')
plt.show()