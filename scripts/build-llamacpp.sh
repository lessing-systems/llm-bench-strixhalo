#!/usr/bin/env bash
# build-llamacpp.sh <backend> [dir] [git-url]
#   backend: cuda | hip | vulkan | cpu
# Clones/updates llama.cpp into [dir] (default ~/llama.cpp-bench) and builds llama-server/llama-bench.
# Optional env: CUDA_ARCH (default 89 = Ada), AMDGPU_TARGET (default gfx1151 = Strix Halo / Radeon 8060S),
#               APPLY_PATCHES=1 to apply patches/*.patch (e.g. the AVX2 Q2_0 CPU kernel)
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(dirname "$HERE")"
BACKEND=${1:?cuda|hip|vulkan|cpu}; DIR=${2:-$HOME/llama.cpp-bench}; URL=${3:-https://github.com/ggml-org/llama.cpp.git}
[[ -d $DIR/.git ]] || git clone --depth 200 "$URL" "$DIR"
cd "$DIR"
if [[ ${APPLY_PATCHES:-0} == 1 ]]; then for p in "$REPO"/patches/*.patch; do git apply --3way "$p" && echo "applied $p"; done; fi
FLAGS=(-DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON -DLLAMA_CURL=OFF)
case $BACKEND in
  cuda)   FLAGS+=(-DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES="${CUDA_ARCH:-89}") ;;
  hip)    FLAGS+=(-DGGML_HIP=ON -DAMDGPU_TARGETS="${AMDGPU_TARGET:-gfx1151}" -DGGML_HIP_ROCWMMA_FATTN=ON) ;;
  vulkan) FLAGS+=(-DGGML_VULKAN=ON) ;;
  cpu)    ;;
  *) echo "unknown backend"; exit 1 ;;
esac
cmake -S . -B build -G Ninja "${FLAGS[@]}"
cmake --build build -j "$(nproc)" --target llama-server llama-bench llama-cli
git log -1 --format='built %h %cd %s'
