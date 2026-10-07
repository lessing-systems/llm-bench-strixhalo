# Hardware fingerprint (2026-10-06)

## OS / kernel
```
Linux strixhalo 7.0.0-34-generic #34~24.04.1-Ubuntu SMP PREEMPT_DYNAMIC Fri Sep  4 15:38:29 UTC 2 x86_64 x86_64 x86_64 GNU/Linux
PRETTY_NAME="Ubuntu 24.04.5 LTS"
```

## CPU
```
CPU(s):                                  32
Model name:                              AMD RYZEN AI MAX+ 395 w/ Radeon 8060S
Thread(s) per core:                      2
Core(s) per socket:                      16
Socket(s):                               1
CPU(s) scaling MHz:                      61%
L3 cache:                                64 MiB (2 instances)
SIMD: avx2 avx512f avx512_vnni avx_vnni 
```

## Memory
```
               total        used        free      shared  buff/cache   available
Mem:             123         118           4           0          64           4
Swap:              0           0           0
```

## GPU
```
============================ ROCm System Management Interface ============================
================================== Memory Usage (Bytes) ==================================
GPU[0]		: GTT Total Memory (B): 128849018880
GPU[0]		: GTT Total Used Memory (B): 12463341568
====================================== Product Info ======================================
GPU[0]		: Card Series: 		AMD Radeon Graphics
GPU[0]		: Card Model: 		0x1586
GPU[0]		: Card Vendor: 		Advanced Micro Devices, Inc. [AMD/ATI]
GPU[0]		: Card SKU: 		STRXLGEN
GPU[0]		: Subsystem ID: 	-0x7fe3
GPU[0]		: Device Rev: 		0xc1
GPU[0]		: Node ID: 		1
GPU[0]		: GUID: 		45881
GPU[0]		: GFX Version: 		gfx1151
================================== End of ROCm SMI Log ===================================
	apiVersion         = 1.4.318
	deviceName         = AMD Radeon Graphics (RADV GFX1151)
	driverName         = radv
	apiVersion         = 1.4.318
	deviceName         = llvmpipe (LLVM 20.1.2, 256 bits)
	driverName         = llvmpipe
```

## llama.cpp
```
6c73b3e Tue Oct 6 11:04:26 2026 +0200 convert : add text_config as fallback [transformers 5.18] (#30040)
master
AMDGPU_TARGETS:UNINITIALIZED=gfx1151
GGML_CUDA:BOOL=OFF
GGML_HIP:BOOL=ON
GGML_NATIVE:BOOL=ON
GGML_VULKAN:BOOL=OFF
```

## Disk
```
rpool/USERDATA/home  1.8T  979G  810G  55% /home
```

## Notes
```
GPU pool: BIOS UMA 2 GiB (VRAM) + GTT 120 GiB (ttm.pages_limit=31457280, set via modprobe conf, not the kernel cmdline)
ROCm 7.2.4 (rocm-core 7.2.4.70204, hip-runtime-amd 7.2.53211), Mesa RADV 25.2.8 (Ubuntu); Nathanw portable build bundles Mesa d18d598e2
Storage: ZFS rpool 1.84T (models on rpool/USERDATA/home); ZFS ARC is evictable and up to ~42 GB while halogen runs
Production: halogen-flash-server 0.15.0 (docker compose), 64 GiB mlocked engine, :8731
```
