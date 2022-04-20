from pickle import NONE
import zmq
import gym, ray
from ray.rllib.agents import ppo,dqn
from gym.spaces import Discrete, Box
import numpy as np
from controller_module import GLOBAL_VALUE
import time
from multiprocessing import Process
import json
import time
import socket
import os
from filelock import FileLock
import sys
def write_for_robot(w):
    
    lock = FileLock("controller_module/.for_robot" + ".lock")
    with lock:
        """利用檔案讓兩個process溝通方便"""   
        f = open("controller_module/.for_robot", "w")
        f.truncate(0)
        f.write(w)
        f.close()
        
def read_for_rl():
    """利用檔案讓兩個process溝通方便""" 
    while True:  
        try:

            lock = FileLock("controller_module/.for_rl" + ".lock")
            with lock:
                f = open("controller_module/.for_rl", "r")
                a=f.read()
                f.close()
            break
        except:
            pass
        time.sleep(0.5)
    return a

class RL_CORE():
    """
    希望讓強化學習保有貪婪策略但是也能從環境互動中修正
    """
    def __init__(self, env_config):
        print("\n\n\被啟動\n\n\n")
        sys.stdout.flush()

        self.greddy_on=True#是否啟動貪婪策略
        self.greedy_percent=5000#每多少次貪婪策略才與真實環境互動10%
        self.step_count=0#計算做出幾次策略決定
        self.action_uuid=0#唯一標示 負責
        self.env_config=env_config
        #self.observation_call_back=self.env_config["observation_call_back"]
        self.Qos_c=1#有多少qos種類根據dscp 6bit=64
        self._raw_action_space=self.env_config["action_space"]
        self._action_space_and_qos=self._raw_action_space*self.Qos_c
        self.action_max=10
        self.action_space =  Box(1, self.action_max, shape=(self._action_space_and_qos,), dtype=np.int)
        
        self.observation_space = Box(0.0, 1, shape=(self.env_config["observation_space"],), dtype=np.float32)
        self.prev_observation=None
        self.prev_observation_no_norm=None
        #self.observation_space=None
        #

    def reset(self):
        self.prev_observation=[0 for _ in range(self.env_config["observation_space"])]
        #self.prev_observation_no_norm=[0 for _ in range(self.env_config["observation_space"])]

        self.observation_space=self.env_config["observation_space"]


        return  self.prev_observation
    def step(self, action):
        print("RL WORK\n\n!!!\n\n")
        sys.stdout.flush()
        self.step_count=self.step_count+1
        #貪婪法則 教導強化學習每次選最好的
        if self.greddy_on and self.step_count%self.greedy_percent!=0 and self.prev_observation_no_norm!=None:
            #根據先前蒐集到的observation也就是真實環境的數據來修正強化學習action
            #讓強化學習保有貪婪的策略
            reward=0
            
            each_len=self.observation_space/4
            for idx, edge_weight_in_tos in enumerate(action):
                tos=192#int(idx/self._raw_action_space)
                edge=int(idx%self._raw_action_space)
                #這邊在乎各個qos的權重
                latency_P=1#int(f"{tos:0{8}b}"[0:2],2)
                loss_P=0#int(f"{tos:0{8}b}"[2:4],2)
                bandwith_P=0#int(f"{tos:0{8}b}"[2:4],2)#頻寬比較特殊 直接使用遺失來評斷是否有符合頻寬需求,如果網路開始遺失代表沒有符合
                jitter_P=0#int(f"{tos:0{8}b}"[4:6],2)

                edge_jitter=self.prev_observation_no_norm[edge+self._raw_action_space*0]
                edge_loss=self.prev_observation_no_norm[edge+self._raw_action_space*1]
                #edge_bandwith=self.prev_observation_no_norm[edge+self._raw_action_space*2]
                edge_latency=self.prev_observation_no_norm[edge+self._raw_action_space*3] 
                #-----
                latency_C=np.interp(edge_latency,(0,GLOBAL_VALUE.MAX_DELAY_ms),(1,-1))
                latency_R=latency_P*latency_C
                #FIXME 這裡可能有問題
                #bandwidth_R=bandwidth_P*np.interp(np.mean(GLOBAL_VALUE.REWARD[src][dst][tos]["detect"]["bandwidth_bytes_per_s"]),(0,10000),comp_size)
                loss_C=np.interp(edge_loss,(0,GLOBAL_VALUE.MAX_Loss_Percent),(1,-1))
                loss_R=loss_P*loss_C
                jitter_C=np.interp(edge_jitter,(0,GLOBAL_VALUE.MAX_Jitter_ms),(1,-1))
                jitter_R=jitter_P*jitter_C

                edge_weight_in_tos_OK=np.interp(edge_weight_in_tos,(0,self.action_max),(100,-100))
                add_reward=((latency_R+jitter_R+loss_R)*(edge_weight_in_tos_OK))

                reward=reward+add_reward
                print(edge_latency,reward,add_reward,edge_weight_in_tos,edge_weight_in_tos_OK,edge+self._raw_action_space*3)
            if np.isnan(reward):
                reward=0
            print(reward)
            return self.prev_observation,reward, False,{}#"""
        #-----------------------------------------------------------------------    
        
        self.action_uuid=self.action_uuid+1
        ac_={"action_uuid":self.action_uuid,"action":action.tolist()}
         
        """step"""
        #這裡要等待更新
        while True:
            write_for_robot(json.dumps(ac_))
            print("RL 這裡要等待網路反饋")
            sys.stdout.flush()
            try:
                m=read_for_rl()
                m_d=json.loads(m)
                if m_d["action_uuid"]==self.action_uuid:
                    break
            except:
                pass
            time.sleep(0.5)
        print("RL接收reward")
        sys.stdout.flush()
        self.prev_observation=m_d["obs"]
        self.prev_observation_no_norm=m_d["obs_no_norm"]
        return m_d["obs"],m_d["reward"], False,{}
  
def entry():
    print("entry start")
    sys.stdout.flush()
    while True:
        try:
            message=read_for_rl()
            print(message,"read_for_rl")
            sys.stdout.flush()
            message_dict=json.loads(message)
            break
        except:
            pass
        time.sleep(5)

    ray.init()
    config = ppo.DEFAULT_CONFIG.copy()
    config["env_config"]=message_dict
    config['model']['fcnet_hiddens'] = [5, 5]
    #config["gamma"]=0.01
    #config["lr"]=0.01
    #config["train_batch_size"]=50
     

    print(config)
    print('啟動AI模組11\n\n')
    sys.stdout.flush()
    trainer = ppo.PPOTrainer(env=RL_CORE, config=config)
    print('啟動AI模組2\n\n')
    sys.stdout.flush()
    """f=open("checkpoint_path","r")
    try:
        file_name=f.read()
        print(file_name,"ok")
        if file_name!="":
            trainer.restore(file_name)
    except:
        #os.remove("checkpoint_path")
        pass"""
    #trainer.restore("/home/lu-yi-hsun/ray_results/PPO_RL_CORE_2021-11-08_21-54-5392o8g072/checkpoint_000002/checkpoint-2")
     
    print('啟動AI模組2\n\n')
     
    while True:
        trainer.train()
        checkpoint_path=trainer.save()
        f=open("checkpoint_path","w+")
        print(checkpoint_path)
        sys.stdout.flush()
        f.write(checkpoint_path)
        f.flush()
        f.close()
        
           

        #  Wait for next request from client
         