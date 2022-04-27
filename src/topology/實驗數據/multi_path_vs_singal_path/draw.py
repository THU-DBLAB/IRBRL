import seaborn as sns
#
import pandas as pd
import matplotlib.pyplot as plt
k_path=4
k_connect_exp=4
grades = {
    "path": [str((int(a/k_connect_exp))+1)+" path" for a in range(k_path*k_connect_exp)],#["1 path", "1 path", "1 path", "1 path","2 path", "2 path", "2 path", "2 path"],
    "iperf -P":[str((int(a%k_connect_exp))+1)+" connect" for a in range(k_path*k_connect_exp)],#["1 connect","2 connect","3 connect","4 connect","1 connect","2 connect","3 connect","4 connect"],
    "bw": [
        0.96,0.96,0.97,0.96, 
        0.96,1.81,1.79,1.59, 
        0.96,1.8,2.65,2.33, 
        0.96,1.86,2.71,2.82],   
}
print(grades)
df = pd.DataFrame(grades)
 
print(df)
#sns.set_theme(style="whitegrid")
sns.set_theme(style="darkgrid")
 
ax = sns.histplot(weights="bw",hue="iperf -P",x="path",multiple="dodge",data=df,shrink=1)

ax.set(xlabel="route at k shortest path", ylabel='Total Bandwith(Mbits/sec)', title="")
plt.savefig('data.png')
#plt.show()

#0 10 20 30 40 thousanl