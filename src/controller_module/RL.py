import zmq
import gym, ray
from ray.rllib.agents import ppo
from gym.spaces import Discrete, Box
import numpy as np
from controller_module import GLOBAL_VALUE
import time
from multiprocessing import Process
import json
import time
import socket
import os
def write_for_robot(w):
        pass   
        f = open("controller_module/.for_robot", "w")
        f.write(w)
        f.close()
        
def read_for_rl():
    while True:  
        try:
            f = open("controller_module/.for_rl", "r")
            a=f.read()
            f.close()
            break
        except:
            pass
        time.sleep(0.5)
    return a

 
class RL_CORE():
    def __init__(self, env_config):
        self.greddy_on=False
 
        self.greedy_percent=95#10%
        self.step_count=0
        self.action_uuid=0
        self.env_config=env_config
        #self.observation_call_back=self.env_config["observation_call_back"]
        self.action_space =  Box(0, 4, shape=(self.env_config["action_space"],), dtype=np.int)
        self.observation_space = Box(0.0, 1, shape=(self.env_config["observation_space"],), dtype=np.float32)
        self.prev_observation=None
    def reset(self):
        self.prev_observation=[0 for _ in range(self.env_config["observation_space"])]
        return  self.prev_observation
    def step(self, action):
        self.step_count=self.step_count+1

        if self.greddy_on and self.step_count%self.greedy_percent!=0:
            pass
            self.prev_observation
            return m_d["obs"],m_d["reward"], False,{}

        self.action_uuid=self.action_uuid+1
        
        ac_={"action_uuid":self.action_uuid,"action":action.tolist()}
        write_for_robot(json.dumps(ac_))
        """step"""
         
        
        #這裡要等待更新
        while True:
            try:
                m=read_for_rl()
                m_d=json.loads(m)
                if m_d["action_uuid"]==self.action_uuid:
                    break
            except:
                pass
            time.sleep(0.5)
        print(m,"RL")
        self.prev_observation=m_d["obs"]


        return m_d["obs"],m_d["reward"], False,{}
  
     
        
        

    def one_row_observation(self):
        return "dsadsadsa"
        pass
        
        jitter_ms=[]
        loss_percent=[]
        bandwidth_bytes_per_s=[]
        latency_ms=[]
        for edge in list(GLOBAL_VALUE.G.edges()):
            edge_id1 = edge[0]
            edge_id2 = edge[1]
            if GLOBAL_VALUE.check_edge_is_link(edge_id1, edge_id2):
                #放入拓樸
                jitter_ms.append(GLOBAL_VALUE.G[edge_id1][edge_id2]["detect"]["jitter_ms"])
                loss_percent.append(GLOBAL_VALUE.G[edge_id1][edge_id2]["detect"]["loss_percent"])
                bandwidth_bytes_per_s.append(GLOBAL_VALUE.G[edge_id1][edge_id2]["detect"]["bandwidth_bytes_per_s"])
                latency_ms.append(GLOBAL_VALUE.G[edge_id1][edge_id2]["detect"]["latency_ms"])
        print("latency_ms",latency_ms)
        try:
            jitter_ms=np.interp(jitter_ms,(0,GLOBAL_VALUE.MAX_Jitter_ms),(0,1))
            loss_percent=np.interp(loss_percent,(0,GLOBAL_VALUE.MAX_Loss_Percent),(0,1))
            bandwidth_bytes_per_s=np.interp(bandwidth_bytes_per_s,(0,GLOBAL_VALUE.MAX_bandwidth_bytes_per_s),(0,1))
            latency_ms=np.interp(latency_ms,(0,GLOBAL_VALUE.MAX_DELAY_TO_LOSS_ms),(0,1))
            ans=np.concatenate((jitter_ms,loss_percent,bandwidth_bytes_per_s,latency_ms))
        except:
            print("one_row_observation error")
            pass
        return ans,len(ans)
  
def entry():
    print("entry start")
    while True:
        try:
            message=read_for_rl()
            print(message,"read_for_rl")
            message_dict=json.loads(message)
            break
        except:
            pass
        time.sleep(5)

    ray.init()
    config = ppo.DEFAULT_CONFIG.copy()
    config["env_config"]=message_dict
    config['model']['fcnet_hiddens'] = [5, 5]

    trainer = ppo.PPOTrainer(env=RL_CORE, config=config)
    #trainer.restore("/home/lu-yi-hsun/ray_results/PPO_RL_CORE_2021-11-08_21-54-5392o8g072/checkpoint_000002/checkpoint-2")
     
    print('啟動AI模組')
    while True:
        trainer.train()
        trainer.save()
        #  Wait for next request from client
         