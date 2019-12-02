#include <linux/module.h>
#include <linux/vermagic.h>
#include <linux/compiler.h>

MODULE_INFO(vermagic, VERMAGIC_STRING);
MODULE_INFO(name, KBUILD_MODNAME);

__visible struct module __this_module
__attribute__((section(".gnu.linkonce.this_module"))) = {
	.name = KBUILD_MODNAME,
	.init = init_module,
#ifdef CONFIG_MODULE_UNLOAD
	.exit = cleanup_module,
#endif
	.arch = MODULE_ARCH_INIT,
};

#ifdef CONFIG_RETPOLINE
MODULE_INFO(retpoline, "Y");
#endif

static const struct modversion_info ____versions[]
__used
__attribute__((section("__versions"))) = {
	{ 0xbdb80144, __VMLINUX_SYMBOL_STR(module_layout) },
	{ 0x55106bd9, __VMLINUX_SYMBOL_STR(ethtool_op_get_link) },
	{ 0x469742ad, __VMLINUX_SYMBOL_STR(eth_mac_addr) },
	{ 0x83cf6431, __VMLINUX_SYMBOL_STR(passthru_features_check) },
	{ 0xe6ce1f72, __VMLINUX_SYMBOL_STR(rtnl_link_unregister) },
	{ 0x9a34c91d, __VMLINUX_SYMBOL_STR(rtnl_link_register) },
	{ 0x79aa04a2, __VMLINUX_SYMBOL_STR(get_random_bytes) },
	{ 0xa8b2ac76, __VMLINUX_SYMBOL_STR(free_netdev) },
	{ 0xd79260f, __VMLINUX_SYMBOL_STR(__put_net) },
	{ 0xd6603e89, __VMLINUX_SYMBOL_STR(rtnl_configure_link) },
	{ 0x69b8d4de, __VMLINUX_SYMBOL_STR(register_netdevice) },
	{ 0xe266ebc9, __VMLINUX_SYMBOL_STR(rtnl_create_link) },
	{ 0x56d48010, __VMLINUX_SYMBOL_STR(rtnl_link_get_net) },
	{ 0x28318305, __VMLINUX_SYMBOL_STR(snprintf) },
	{ 0x6b640864, __VMLINUX_SYMBOL_STR(nla_strlcpy) },
	{ 0x872b03ea, __VMLINUX_SYMBOL_STR(rtnl_nla_parse_ifla) },
	{ 0x999e8297, __VMLINUX_SYMBOL_STR(vfree) },
	{ 0x663531f, __VMLINUX_SYMBOL_STR(netif_carrier_off) },
	{ 0xdb7305a1, __VMLINUX_SYMBOL_STR(__stack_chk_fail) },
	{ 0xed433664, __VMLINUX_SYMBOL_STR(__per_cpu_offset) },
	{ 0x17de3d5, __VMLINUX_SYMBOL_STR(nr_cpu_ids) },
	{ 0x1fb81e83, __VMLINUX_SYMBOL_STR(cpumask_next) },
	{ 0x59c1d110, __VMLINUX_SYMBOL_STR(__cpu_possible_mask) },
	{ 0xbd671048, __VMLINUX_SYMBOL_STR(__alloc_percpu_gfp) },
	{ 0x2b63566c, __VMLINUX_SYMBOL_STR(netif_carrier_on) },
	{ 0xd6ee688f, __VMLINUX_SYMBOL_STR(vmalloc) },
	{ 0xd58f6174, __VMLINUX_SYMBOL_STR(kfree_skb) },
	{ 0x53569707, __VMLINUX_SYMBOL_STR(this_cpu_off) },
	{ 0xf033bf87, __VMLINUX_SYMBOL_STR(dev_forward_skb) },
	{ 0x2469810f, __VMLINUX_SYMBOL_STR(__rcu_read_unlock) },
	{ 0x8d522714, __VMLINUX_SYMBOL_STR(__rcu_read_lock) },
	{ 0xc9ec4e21, __VMLINUX_SYMBOL_STR(free_percpu) },
	{ 0xc91352e2, __VMLINUX_SYMBOL_STR(ether_setup) },
	{ 0x52ab8eef, __VMLINUX_SYMBOL_STR(unregister_netdevice_queue) },
	{ 0xbdfb6dbb, __VMLINUX_SYMBOL_STR(__fentry__) },
};

static const char __module_depends[]
__used
__attribute__((section(".modinfo"))) =
"depends=";


MODULE_INFO(srcversion, "84F1B07D3F63EDE9C14BEBF");
