#include <linux/build-salt.h>
#include <linux/module.h>
#include <linux/vermagic.h>
#include <linux/compiler.h>

BUILD_SALT;

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
	{ 0x9cbc70c9, "module_layout" },
	{ 0xa49f0002, "ethtool_op_get_link" },
	{ 0x581a77c3, "eth_mac_addr" },
	{ 0xb4a8bee8, "passthru_features_check" },
	{ 0x7fdece5b, "rtnl_link_unregister" },
	{ 0x2037d7cb, "rtnl_link_register" },
	{ 0x4c9d28b0, "phys_base" },
	{ 0x1ed8b599, "__x86_indirect_thunk_r8" },
	{ 0x559b27f8, "xdp_do_flush_map" },
	{ 0xb8be1307, "napi_complete_done" },
	{ 0x4566f258, "napi_gro_receive" },
	{ 0x38961b35, "eth_type_trans" },
	{ 0x7260e249, "___preempt_schedule_notrace" },
	{ 0x4629334c, "__preempt_count" },
	{ 0x80a8e8e, "__cpu_online_mask" },
	{ 0x7a2af7b4, "cpu_number" },
	{ 0xdc34a927, "__tracepoint_xdp_exception" },
	{ 0x5c2bcd37, "bpf_warn_invalid_xdp_action" },
	{ 0x88e1d0f0, "page_frag_free" },
	{ 0x3ced658e, "xdp_do_redirect" },
	{ 0xc2f794f4, "consume_skb" },
	{ 0xd8e67c5c, "skb_headers_offset_update" },
	{ 0x643789db, "skb_copy_header" },
	{ 0x3052e00e, "skb_put" },
	{ 0x890c840d, "build_skb" },
	{ 0xd41e951e, "skb_copy_bits" },
	{ 0x7cd8d75e, "page_offset_base" },
	{ 0x97651e6c, "vmemmap_base" },
	{ 0xef62270f, "alloc_pages_current" },
	{ 0x2ea2c95c, "__x86_indirect_thunk_rax" },
	{ 0xc7aabe00, "bpf_redirect_info" },
	{ 0x999e8297, "vfree" },
	{ 0xc4cbba1d, "netdev_update_features" },
	{ 0xd7e53ecc, "bpf_prog_put" },
	{ 0x1ad8149a, "__dev_kfree_skb_any" },
	{ 0x653fbf80, "__per_cpu_offset" },
	{ 0x6c33d5e, "netif_rx" },
	{ 0x378c04d4, "__dev_forward_skb" },
	{ 0x10042ed3, "xdp_return_frame_rx_napi" },
	{ 0xc917e655, "debug_smp_processor_id" },
	{ 0x54ad65cc, "__napi_schedule" },
	{ 0x493e362a, "napi_schedule_prep" },
	{ 0xd2b09ce5, "__kmalloc" },
	{ 0x17de3d5, "nr_cpu_ids" },
	{ 0x90552928, "cpumask_next" },
	{ 0xd22c7f94, "__cpu_possible_mask" },
	{ 0xbd671048, "__alloc_percpu_gfp" },
	{ 0xce87d758, "netif_carrier_on" },
	{ 0xd6ee688f, "vmalloc" },
	{ 0x51c122f6, "netif_napi_del" },
	{ 0x609f1c7e, "synchronize_net" },
	{ 0x8c0d859a, "napi_hash_del" },
	{ 0xac2119c, "napi_disable" },
	{ 0x7aa1756e, "kvfree" },
	{ 0xdbf17652, "_raw_spin_lock" },
	{ 0x301fa007, "_raw_spin_unlock" },
	{ 0x43ef5f00, "netif_napi_add" },
	{ 0xc5bc25de, "kvmalloc_node" },
	{ 0x90a8752c, "xdp_rxq_info_unreg" },
	{ 0x6fd51ac7, "xdp_rxq_info_reg" },
	{ 0x2f795fe4, "xdp_rxq_info_reg_mem_model" },
	{ 0x307246e7, "xdp_rxq_info_is_reg" },
	{ 0x2469810f, "__rcu_read_unlock" },
	{ 0x8d522714, "__rcu_read_lock" },
	{ 0xc1a582ac, "kfree_skb" },
	{ 0x1a3fb373, "xdp_return_frame" },
	{ 0xc9ec4e21, "free_percpu" },
	{ 0x37a0cba, "kfree" },
	{ 0x6463bd04, "ether_setup" },
	{ 0xdb7305a1, "__stack_chk_fail" },
	{ 0x79aa04a2, "get_random_bytes" },
	{ 0xb1f19164, "free_netdev" },
	{ 0xe89fe584, "__put_net" },
	{ 0x849129f1, "rtnl_configure_link" },
	{ 0xac677165, "netif_carrier_off" },
	{ 0xb348a850, "ex_handler_refcount" },
	{ 0xdaef1c76, "register_netdevice" },
	{ 0xc9089e33, "rtnl_create_link" },
	{ 0xecd7fac2, "rtnl_link_get_net" },
	{ 0x28318305, "snprintf" },
	{ 0x6b640864, "nla_strlcpy" },
	{ 0xe1e7e40c, "rtnl_nla_parse_ifla" },
	{ 0x201087da, "unregister_netdevice_queue" },
	{ 0xbdfb6dbb, "__fentry__" },
};

static const char __module_depends[]
__used
__attribute__((section(".modinfo"))) =
"depends=";


MODULE_INFO(srcversion, "A2BD0EBC49DA7BF014BCDF6");
