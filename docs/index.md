
# 安裝

只兼容linux
 
核心(system)模式運做的openvswitch:Open vSwitch 版本要高於2.10 ,Linux kernel版本要高於4.15才支援meter table
user space 模式運做的openvswitch:Open vSwitch 版本要高於2.7,並且要加上DPDK(Data Plane Development Kit)才能順利運作
 
## 安裝依賴函數庫

### for cpython

```bash
sudo pip3 install -r requirements.txt
```
 
### for pypy

推薦pypy 效能高5倍

```bash
sudo pypy3 -m pip install -r requirements.txt
```


## 修改linux veth驅動程式

!!! note
    目的:為了得到正確交換機網卡速度以計算該鏈路剩餘頻寬有多少

當初遇到miniet在模擬的時候無法修改個別veth交換機網卡資訊,導致Openvswitch回傳curr_speed(Kbps)都是固定數值,無法完美模擬不同網速的交換機,在上傳OFPMP_PORT_DESC時有不同
的"curr"(請翻閱openflow1.5.1規格書69頁的ofp_port_features有詳細介紹)與"curr_speed"

嘗試了ethtool也無法修正port 資訊
由於linux veth驅動程式無法修改port交換機的速度與支持的所以我們需要修改veth的驅動程式.

### 安裝ethtool

#### 下載原始碼並解壓縮
    原始碼網站:https://mirrors.edge.kernel.org/pub/software/network/ethtool/

#### 進入ethtool原始碼

```bash
./configure
make
make install
```
#### 測試

啟動mininet一個拓樸 

ifconfig後查詢openvswitch交換機的interface name,舉例s1-eth1

執行這段指令可以發現設定失敗 因為veth驅動程式不允許我們設定veth的數值,所以我們須要修改驅動程式的程式碼

```bash
sudo ethtool -s s1-eth1 speed 100
```

### 修改veth.c

#### 查詢自己linux kernel版本

```
uname -a
```

我的核心是4.19.66你的可能跟我不一樣 

```
Linux ML 4.19.66-1-MANJARO #1 SMP PREEMPT Fri Aug 9 18:01:53 UTC 2019 x86_64 GNU/Linux
```

#### 根據你核心版本下載veth原始碼


一定要跟你核心版本一樣,不然可能發生錯誤

底下的4.19.66改成你的核心版本

下載你自己版本的veth.c

```bash
wget https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/plain/drivers/net/veth.c?h=v4.19.66 -O veth.c
```

開始修改驅動程式 以下修改都是在veth.c檔案,接下來都塞入標示黃色部份的程式碼

#### Singly linked list

先宣告Singly linked list實做的方法

```c hl_lines="39 40 41 42 43 44 45 46 47 48 49 50 51 52 53 54 55 56 57 58 59 60 61 62 63 64 65 66 67 68 69 70 71 72 73 74 75 76 77 78 79 80 81 82 83 84 85 86 87 88 89 90 91 92 93 94 95 96 97 98 99 100 101 102 103 104 105 106 107 108 109 110 111 112 113 114 115 116 117 118 119"
/*
 *  drivers/net/veth.c
 *
 *  Copyright (C) 2007 OpenVZ http://openvz.org, SWsoft Inc
 *
 * Author: Pavel Emelianov <xemul@openvz.org>
 * Ethtool interface from: Eric W. Biederman <ebiederm@xmission.com>
 *
 */

#include <linux/netdevice.h>
#include <linux/slab.h>
#include <linux/ethtool.h>
#include <linux/etherdevice.h>
#include <linux/u64_stats_sync.h>

#include <net/rtnetlink.h>
#include <net/dst.h>
#include <net/xfrm.h>
#include <net/xdp.h>
#include <linux/veth.h>
#include <linux/module.h>
#include <linux/bpf.h>
#include <linux/filter.h>
#include <linux/ptr_ring.h>
#include <linux/bpf_trace.h>

#define DRV_NAME "veth"
#define DRV_VERSION "1.0"

#define VETH_XDP_FLAG BIT(0)
#define VETH_RING_SIZE 256
#define VETH_XDP_HEADROOM (XDP_PACKET_HEADROOM + NET_IP_ALIGN)

/* Separating two types of XDP xmit */
#define VETH_XDP_TX BIT(0)
#define VETH_XDP_REDIR BIT(1)

typedef struct node
{
	struct node *next;
	int ifindex;
	struct ethtool_link_settings veth_ethtool;
} Node;

typedef struct list
{
	Node *head;
} List;

static List list;
static Node *node;
static int node_number = 0;

Node *create_node(int value)
{
	Node *node = (Node *)vmalloc(sizeof(Node));
	node->next = NULL;
	node->ifindex = value;
	node->veth_ethtool.speed = SPEED_10000;
	node->veth_ethtool.duplex = DUPLEX_FULL;
	node->veth_ethtool.port = PORT_TP;
	return node;
}

Node *get_node(List *list, int ifindex)
{
	 
	Node *innode = list->head;

	while (innode != NULL)
	{
		if (innode->ifindex == ifindex)
		{
			return innode;
		}
		innode = innode->next;
	}
 

	return node;
}


static int remove_list_node_by_key(List *list, int ifindex)
{
	 
	Node *node = (list->head);
	if (node->ifindex == ifindex)
	{
		list->head = node->next;

		vfree(node);
		node_number = node_number - 1;
		return 0;
	}
	while (node != NULL)
	{

		Node *next_node = node->next;

		if (next_node != NULL)
		{
			if (next_node->ifindex == ifindex)
			{

				node->next = node->next->next;

				vfree(next_node);
				node_number = node_number - 1;
				return 0;
			}
		}
		else
		{
			return -1;
		}
		node = node->next;
	}

	return -1;
}

```

可以看看ethtool_link_settings struct 可以設定的參數
由於我只在乎設定speed,duplex,port這幾個參數所以,veth_get_link_ksettings,veth_set_link_ksettings只實做這幾個,如果有特殊需求的人可以自己加

在linux 原始碼
linux/include/uapi/linux/ethtool.h

https://github.com/torvalds/linux/blob/a2d79c7174aeb43b13020dd53d85a7aefdd9f3e5/include/uapi/linux/ethtool.h#L1848

```c
struct ethtool_link_settings {
	__u32	cmd;
	__u32	speed;
	__u8	duplex;
	__u8	port;
	__u8	phy_address;
	__u8	autoneg;
	__u8	mdio_support;
	__u8	eth_tp_mdix;
	__u8	eth_tp_mdix_ctrl;
	__s8	link_mode_masks_nwords;
	__u8	transceiver;
	__u8	reserved1[3];
	__u32	reserved[7];
	__u32	link_mode_masks[0];
	/* layout of link_mode_masks fields:
	 * __u32 map_supported[link_mode_masks_nwords];
	 * __u32 map_advertising[link_mode_masks_nwords];
	 * __u32 map_lp_advertising[link_mode_masks_nwords];
	 */
};
#endif /* _LINUX_ETHTOOL_H */

```

#### veth_open

linux 在啟動veth 會呼叫veth_open,以ifindex當作key,在link list中新增一個節點

塞入標示黃色部份的程式碼

```c hl_lines="22 23 24 25 26 27 28 29 30 31"
static int veth_open(struct net_device *dev)
{
	struct veth_priv *priv = netdev_priv(dev);
	struct net_device *peer = rtnl_dereference(priv->peer);
	int err;

	if (!peer)
		return -ENOTCONN;

	if (priv->_xdp_prog)
	{
		err = veth_enable_xdp(dev);
		if (err)
			return err;
	}

	if (peer->flags & IFF_UP)
	{
		netif_carrier_on(dev);
		netif_carrier_on(peer);
	}
		if (node_number == 0)
	{
		node = list.head = create_node(dev->ifindex);
	}
	else
	{
		node->next = create_node(dev->ifindex);
		node = node->next;
	}
	node_number = node_number + 1;

	return 0;
}
```

#### veth_close

linux 在關閉veth 會呼叫veth_close,以ifindex當作key,在link list中刪除該節點

塞入標示黃色部份的程式碼


```c hl_lines="13"
static int veth_close(struct net_device *dev)
{
	struct veth_priv *priv = netdev_priv(dev);
	struct net_device *peer = rtnl_dereference(priv->peer);

	netif_carrier_off(dev);
	if (peer)
		netif_carrier_off(peer);

	if (priv->_xdp_prog)
		veth_disable_xdp(dev);

	remove_list_node_by_key(&list, dev->ifindex);
	return 0;
}
```
 
#### veth_get_link_ksettings

這裡是veth驅動在回答硬體參數的地方

改掉這裡的程式碼變成下面這樣

```c hl_lines="4 5 6 7 8"
static int veth_get_link_ksettings(struct net_device *dev,
				   struct ethtool_link_ksettings *cmd)
{
	Node *node = get_node(&list, dev->ifindex);
	cmd->base.speed = node->veth_ethtool.speed;
	cmd->base.duplex = node->veth_ethtool.duplex;
	cmd->base.port = node->veth_ethtool.port;

	return 0;
}
```


#### veth_ethtool_ops

註冊veth_ethtool_ops

根據
[ethtool.h](https://github.com/torvalds/linux/blob/2a11c76e5301dddefcb618dac04f74e6314df6bc/include/linux/ethtool.h#L399)
的原始碼我們可以知道ethtool的set_link_ksettings其實是可以設定參數但是veth.c沒有實做出來,所以我們剛剛才無法設定

所以必須填入.set_link_ksettings =veth_set_link_ksettings,
等等在實做veth_set_link_ksettings

```c hl_lines="2"
static const struct ethtool_ops veth_ethtool_ops = {
	.set_link_ksettings = veth_set_link_ksettings,
	.get_drvinfo = veth_get_drvinfo,
	.get_link = ethtool_op_get_link,
	.get_strings = veth_get_strings,
	.get_sset_count = veth_get_sset_count,
	.get_ethtool_stats = veth_get_ethtool_stats,
	.get_link_ksettings = veth_get_link_ksettings,

};
```

#### veth_set_link_ksettings

實做veth_set_link_ksettings

[ethtool.h](https://github.com/torvalds/linux/blob/2a11c76e5301dddefcb618dac04f74e6314df6bc/include/linux/ethtool.h#L399)裡面有規定函數輸入型態

```c hl_lines="1 2 3 4 5 6 7 8 9 10 11 12"
static int veth_set_link_ksettings(struct net_device *dev,
					const struct ethtool_link_ksettings *cmd)
{
	Node *node = get_node(&list, dev->ifindex);
	node->veth_ethtool.speed = cmd->base.speed;
	node->veth_ethtool.duplex = cmd->base.duplex;
	node->veth_ethtool.port = cmd->base.port;
	return 0;
}
```

### 撰寫Makefile

新增檔案命名Makefile
注意複製的時候有可能tab變成space導致無法編譯
 
```Makefile tab=
obj-m += veth.o
all:
	make -C /lib/modules/$(shell uname -r)/build M=$(PWD) modules
clean:
	make -C /lib/modules/$(shell uname -r)/build M=$(PWD) clean
```


###編譯驅動程式

做到這裡你有兩個檔案veth.c 與 Makefile

執行之後可以看到產生veth.ko檔案
```bash
make
```

如果原本就有veth驅動程式 請刪除
```
sudo rmmod veth
```

這邊安裝驅動程式
```bash
sudo insmod veth.ko
```

### 測試
啟動mininet一個拓樸 

ifconfig後查詢openvswitch交換機的interface name,舉例s1-eth1

先查詢s1-eth1的資訊
```bash
sudo ethtool s1-eth1
```

修該s1-eth1 post速度
```bash
sudo ethtool -s s1-eth1 speed 100
```
可以發現真的可以修改了!!


 