# llama.cpp first pass on Strix Halo (profile strix-halo-395, CTX=131072 from the profile). Speed + long-context probe only.
# Run: BENCH_HW=strix-halo-395 scripts/run.sh queues/strix-halo-llamacpp.sh
# Needs the three llama.cpp builds from the profile header and the GGUFs listed there. Edit the config names to
# what you have downloaded. MTP head = unsloth re-upload of 2026-10-05 unless MTPHEAD is set.
# 1) backend shoot-out on the same UD-IQ4_XS trunk: HIP vs Vulkan vs the Nathanw Vulkan fork, and MTP off
speed fn-udiq4xs    "MTPN=3" fn-udiq4xs-hip-mtp3
speed fn-udiq4xs-vk "MTPN=3" fn-udiq4xs-vk-mtp3
speed fn-udiq4xs-nw "MTPN=3" fn-udiq4xs-nw-mtp3
speed fn-udiq4xs    "NOMTP=1" fn-udiq4xs-hip-nomtp
# 2) smaller GSQ-RCO quants that fit with more headroom
speed fn-iq3s       "MTPN=3" fn-iq3s-hip-mtp3
speed fn-iq3s-vk    "MTPN=3" fn-iq3s-vk-mtp3
speed swfn-iq3xxs   "MTPN=3" swfn-iq3xxs-hip-mtp3
speed swfn-iq3xxs-vk "MTPN=3" swfn-iq3xxs-vk-mtp3
# 3) dense reference
speed swift-iq3s    "MTPN=2" swift27b-iq3s-hip-mtp2
