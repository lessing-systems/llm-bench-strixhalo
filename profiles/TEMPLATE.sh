# Hardware profile TEMPLATE. Copy to profiles/<hw-id>.sh (see docs/GUIDELINES.md for naming), then:
#   export BENCH_HW=<hw-id>
#
# Sourced by scripts/serve.sh. Provide:
#   LLAMA_SERVER   path to llama-server (default backend build for this box)
#   THREADS        CPU threads for llama-server (-t); for CPU-offloaded MoE use #physical cores
#   gpu_mem_used() optional: print GPU memory in use (MiB) - default uses nvidia-smi
#   config_<name>  one function per model config: set MODEL=<gguf> and ARGS=(...); optionally BIN=<other llama-server>
# Also export BENCH_GPU_MEM_CMD for bench.py if not on NVIDIA (same command as gpu_mem_used).

MODELS=${MODELS:-$HOME/models}
LLAMA_SERVER=${LLAMA_SERVER:-$HOME/llama.cpp-bench/build/bin/llama-server}
THREADS=8

# gpu_mem_used() { echo 0; }

# Dense model, fully offloaded:
config_example-dense() { MODEL=$MODELS/some-model.gguf; ARGS=(-ngl 99 -t $THREADS); }

# MoE with routed experts kept in system RAM (tune NCMOE so VRAM is ~90% used, threads = physical cores):
config_example-moe()   { MODEL=$MODELS/some-moe-00001-of-00002.gguf; ARGS=(-ngl 99 --n-cpu-moe ${NCMOE:-30} -t ${THREADS} -b 4096 -ub 4096); }
