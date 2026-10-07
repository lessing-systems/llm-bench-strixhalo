# Hardware profile: Strix Halo 395, 128 GB (verified 2026-10-06, hw-id strix-halo-395)
# AMD Ryzen AI Max+ 395 "Strix Halo", Radeon 8060S iGPU (RDNA 3.5, gfx1151), 128 GB LPDDR5X unified memory
# (~256 GB/s, OS sees 123 GB), 16C/32T Zen 5. Ubuntu 24.04, kernel 7.0, ttm.pages_limit=31457280 (~120 GB GPU-addressable).
# BIOS UMA carve-out is only 2 GB; the GPU pool is GTT (120 GB, ttm.pages_limit). Memory probe reads GTT, not VRAM.
#
# halogen-flash-server (the winner, see results/strix-halo-395/REPORT.md) is NOT launched via serve.sh: it runs under
# docker compose from launch/. Benchmark it with scripts/external_bench.sh (queues/strix-halo-halogen.sh), or point
# bench.py at any running server:
#   python3 bench/bench.py speed --url http://127.0.0.1:8731 --tag halogen-baseline
# A halogen engine holds ~110 GB, so nothing else fits beside it.
# Build the llama.cpp variants with scripts/build-llamacpp.sh hip|vulkan <dir> (paths below are the defaults).
#
# Key differences vs a discrete-GPU box (see docs/GUIDELINES.md):
#  * one unified memory pool: -ngl 99 for everything, no --n-cpu-moe needed
#  * ~3x less bandwidth than an RTX 4080 SUPER: dense 27B decodes ~3x slower; big sparse MoE is the sweet spot
#  * build both HIP (ROCm) and Vulkan backends and benchmark both

MODELS=${MODELS:-$HOME/models}
LLAMA_SERVER=${BENCH_LLAMA_SERVER:-$HOME/llama.cpp-bench/build/bin/llama-server}     # fresh: scripts/build-llamacpp.sh hip ~/llama.cpp-bench
VULKAN_SERVER=${VULKAN_SERVER:-$HOME/llama.cpp-vulkan/build/bin/llama-server}  # fresh: scripts/build-llamacpp.sh vulkan ~/llama.cpp-vulkan
NATHANW_SERVER=${NATHANW_SERVER:-$HOME/strix-halo-llamacpp/vulkan/llama-server}       # Nathanw1014/strix-halo-llamacpp portable (Vulkan, bundled RADV); use the top-level launcher, not bin/
THREADS=16
: "${CTX:=131072}"; export CTX    # user requirement on the test box: >= 128k context
: "${PREP_MEM:=1}"                 # drop ZFS ARC + compact before each load (see serve.sh)

gpu_mem_used() { awk '{printf "%d\n",$1/1048576}' /sys/class/drm/${GPU_CARD:-card1}/device/mem_info_gtt_used; }
export BENCH_GPU_MEM_CMD="awk '{printf \"%d\\n\",\$1/1048576}' /sys/class/drm/${GPU_CARD:-card1}/device/mem_info_gtt_used"

# Flash-Next MTP heads. The unsloth heads were re-uploaded 2026-10-05 (same size, new weights); the copy in
# Qwen3.8-UD_IQ4_XS/MTP/ (2026-09-18) is the OLD one. Pick with MTPHEAD=<path>.
FN_MTP_NEW=$MODELS/flashnext-mtp/unsloth-20261005/MTP/mtp-Qwen3.8-Flash-Next-Q8_0.gguf
FN_MTP_OLD=$MODELS/Qwen3.8-UD_IQ4_XS/MTP/mtp-Qwen3.8-Flash-Next-Q8_0.gguf
FN_MTP_SHARED=$MODELS/Qwen3.8-UD_IQ4_XS/MTP/mtp-Qwen3.8-Flash-Next-shared-Q8_0.gguf   # unchanged upstream
# -b == -ub ON PURPOSE: HIP on gfx1151 / ROCm 7.2.x silently corrupts long-context output when n_ubatch < n_batch
# (ggml-org/llama.cpp#27579, fix #27311 unmerged as of 2026-10-06). Same values on Vulkan for a fair comparison.
# speculative head only when speculative decoding is on (serve.sh speed mode without NOMTP=1)
# -lm none: on this ZFS box mmap loading is page-fault bound (Flash-Next UD-IQ4_XS: >20 min, never finished; none: 66 s warm).
# The 28.8 GB n-gram/per-layer-embedding table then stays resident in host RAM (fits: ~89 GB total at 128k), so no -lzm.
fn_args() { ARGS=(-ngl 99 -t $THREADS -b 2048 -ub 2048 -lm none)
            [[ ${NOMTP:-0} != 1 && ${DFLASH:-0} != 1 && $MODE != eval ]] && ARGS+=(-md "${MTPHEAD:-$FN_MTP_NEW}"); }

# Nathanw build (2026-09-16) predates upstream's -lzm spelling (only matters if a config adds -lzm)
nw_args() { BIN=$NATHANW_SERVER; local i; for i in "${!ARGS[@]}"; do [[ ${ARGS[$i]} == -lzm ]] && ARGS[$i]=--tensor-read-lazy; done; }

# --- existing GGUF on this box: unsloth Flash-Next UD-IQ4_XS (trunk unchanged upstream since 2026-09-01), 94 GB
FN_UD=$MODELS/Qwen3.8-UD_IQ4_XS/UD-IQ4_XS/Qwen3.8-Flash-Next-UD-IQ4_XS-00001-of-00003.gguf
config_fn-udiq4xs()    { MODEL=$FN_UD; fn_args; }
config_fn-udiq4xs-vk() { config_fn-udiq4xs; BIN=$VULKAN_SERVER; }
config_fn-udiq4xs-nw() { config_fn-udiq4xs; nw_args; }

# --- ISTA GSQ-RCO Flash-Next IQ3_S (83.6 GB; the n-gram shard 00002 is identical across ISTA quants)
config_fn-iq3s()       { MODEL=$MODELS/flashnext/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf; fn_args; }
config_fn-iq3s-vk()    { config_fn-iq3s; BIN=$VULKAN_SERVER; }
config_fn-iq3s-nw()    { config_fn-iq3s; nw_args; }

# --- Swift-1.5 Flash-Next (UkisAI post-train, ~30-60% fewer thinking tokens) GSQ-RCO IQ3_XXS (76 GB)
config_swfn-iq3xxs()   { MODEL=$MODELS/swift-flashnext/IQ3_XXS/Swift-Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00001-of-00002.gguf; fn_args; }
config_swfn-iq3xxs-vk(){ config_swfn-iq3xxs; BIN=$VULKAN_SERVER; }
config_swfn-iq3xxs-nw(){ config_swfn-iq3xxs; nw_args; }

# --- dense reference: Swift-1.5 Qwen3.8-27B GSQ-RCO IQ3_S with built-in MTP (12.1 GB)
config_swift-iq3s()    { MODEL=$MODELS/swift27b/Swift-1.5-Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf; ARGS=(-ngl 99 -t $THREADS -b 2048 -ub 2048); }
config_swift-iq3s-vk() { config_swift-iq3s; BIN=$VULKAN_SERVER; }
