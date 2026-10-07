#!/usr/bin/env bash
# hwinfo.sh [llama.cpp dir]  -> prints a markdown hardware fingerprint; save it as results/<hw>/hardware.md
LLAMA_DIR=${1:-}
echo "# Hardware fingerprint ($(date -I))"
echo; echo '## OS / kernel'; echo '```'; uname -a; grep -E '^(PRETTY_NAME)' /etc/os-release 2>/dev/null
grep -qi microsoft /proc/version && echo "WSL2: yes ($(cat /proc/sys/kernel/osrelease))"; echo '```'
echo; echo '## CPU'; echo '```'; lscpu | grep -E '^(Model name|CPU\(s\)|Thread\(s\) per core|Core\(s\) per socket|Socket\(s\)|L3 cache)'
echo "SIMD: $(grep -o -w -E 'avx2|avx512f|avx512_vnni|avx_vnni|amx_tile' /proc/cpuinfo | sort -u | tr '\n' ' ')"; echo '```'
echo; echo '## Memory'; echo '```'; free -g; [[ -f /mnt/c/Users/$USER/.wslconfig ]] && { echo "--- .wslconfig"; cat /mnt/c/Users/$USER/.wslconfig; echo; }; echo '```'
echo; echo '## GPU'; echo '```'
if command -v nvidia-smi >/dev/null; then nvidia-smi --query-gpu=name,memory.total,driver_version,pcie.link.gen.current,pcie.link.width.current --format=csv; fi
if command -v rocm-smi >/dev/null; then rocm-smi --showproductname --showmeminfo vram --showmeminfo gtt 2>/dev/null | grep -v '^=*$'; fi
if command -v vulkaninfo >/dev/null; then vulkaninfo --summary 2>/dev/null | grep -E 'deviceName|driverName|apiVersion' | head -6; fi
echo '```'
if [[ -n $LLAMA_DIR && -d $LLAMA_DIR/.git ]]; then
  echo; echo '## llama.cpp'; echo '```'; git -C "$LLAMA_DIR" log -1 --format='%h %cd %s'; git -C "$LLAMA_DIR" branch --show-current
  grep -E '^(GGML_(CUDA|HIP|VULKAN|NATIVE)|CMAKE_CUDA_ARCHITECTURES|AMDGPU_TARGETS|GPU_TARGETS):' "$LLAMA_DIR/build/CMakeCache.txt" 2>/dev/null; echo '```'
fi
echo; echo '## Disk'; echo '```'; df -h "${MODELS_DIR:-$HOME}" | tail -1; echo '```'
