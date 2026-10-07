#!/usr/bin/env bash
# serve.sh <config> <mode> [extra llama-server args...]
#
# Starts llama-server for a model config defined in the active hardware profile,
# in tmux session $BENCH_SESSION (default BENCH) on port $PORT (default 8091), and waits until healthy.
#
#   <config>  a function config_<config> in profiles/$BENCH_HW.sh
#   <mode>    eval  : -np 4 --kv-unified, no speculative decoding (throughput for the eval suite)
#             speed : -np 1 + speculative decoding (single-stream, what an interactive user sees)
#             prod  : same as speed
#
# Env knobs (all optional):
#   BENCH_HW   hardware profile name (profiles/<name>.sh)      [required]
#   CTX        context size (default 65536)       KV  KV cache type (default q8_0)
#   NOMTP=1    disable speculative decoding in speed mode
#   MTPN       MTP draft tokens (default 2)       PMIN  --spec-draft-p-min (default 0.0)
#   SPECTYPE   e.g. draft-mtp | draft-mtp,ngram-mod
#   DFLASH=1   use an external DFlash draft: DFLASH_MODEL=<gguf>, DFN=<n-max> (default 7)
#   SPECSAMP   --spec-draft-sampling greedy|probabilistic (rejection sampling at temp > 0; upstream default greedy)
#   PREP_MEM=1 drop caches + compact memory before starting (profiles for unified-memory boxes set it)
#   MTPHEAD    separate MTP head file, for profiles whose configs pass -md (e.g. Flash-Next)
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(dirname "$HERE")"
CFG=$1; MODE=$2; shift 2
: "${BENCH_HW:?set BENCH_HW to a profile name in $REPO/profiles}"
PROFILE="$REPO/profiles/$BENCH_HW.sh"
[[ -f $PROFILE ]] || { echo "no profile $PROFILE"; exit 1; }
PORT=${PORT:-8091}
SESSION=${BENCH_SESSION:-BENCH}
LOGDIR=${BENCH_LOGDIR:-$REPO/results/$BENCH_HW/logs}; mkdir -p "$LOGDIR"

# defaults a profile may override
LLAMA_SERVER=llama-server
THREADS=4
gpu_mem_used() { nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | head -1; }
source "$PROFILE"

declare -F "config_$CFG" >/dev/null || { echo "unknown config '$CFG' (define config_$CFG in $PROFILE)"; exit 1; }
BIN=$LLAMA_SERVER; MODEL=""; ARGS=()
"config_$CFG"
[[ -f $MODEL ]] || { echo "model not found: $MODEL"; exit 1; }

COMMON=(--host 0.0.0.0 --port "$PORT" -c "${CTX:-65536}" -fa on --jinja
        --cache-type-k "${KV:-q8_0}" --cache-type-v "${KV:-q8_0}"
        --no-context-shift --reasoning-format auto
        --temp 1 --top-p 0.95 --top-k 20 --min-p 0.0 --repeat-penalty 1.0 --presence-penalty 0.0 --metrics)
case $MODE in
  eval) ARGS+=(-np 4 --kv-unified) ;;
  speed|prod)
    ARGS+=(-np 1)
    if [[ ${DFLASH:-0} == 1 ]]; then
      ARGS+=(-md "${DFLASH_MODEL:?set DFLASH_MODEL}" --spec-type draft-dflash --spec-draft-n-max "${DFN:-7}" -ngld 99)
    elif [[ ${NOMTP:-0} != 1 ]]; then
      ARGS+=(--spec-type "${SPECTYPE:-draft-mtp}" --spec-draft-n-max "${MTPN:-2}" --spec-draft-p-min "${PMIN:-0.0}")
      [[ -n ${SPECSAMP:-} ]] && ARGS+=(--spec-draft-sampling "$SPECSAMP")
    fi ;;
  *) echo "mode must be eval|speed|prod"; exit 1 ;;
esac

# stop the previous bench server and wait until it has released the port / VRAM
tmux kill-session -t "=$SESSION" 2>/dev/null; sleep 2
for i in $(seq 1 30); do pgrep -f "^[^ ]*llama-server .*--port $PORT( |$)" >/dev/null || break; sleep 1; done
sleep 3
# unified-memory boxes: drop the file cache (ZFS ARC) and compact memory, or a large load can stall for many
# minutes in compaction at 100% of one core (seen on Strix Halo after halogen exits). PREP_MEM=0 to skip.
if [[ ${PREP_MEM:-0} == 1 ]]; then sync; echo 3 | sudo -n tee /proc/sys/vm/drop_caches >/dev/null
  echo 1 | sudo -n tee /proc/sys/vm/compact_memory >/dev/null; fi

LOG="$LOGDIR/server-$CFG-$MODE.log"
CMD="$BIN -m $MODEL ${COMMON[*]} ${ARGS[*]} $*"
echo "$CMD" > "$LOG"
# record what is running, so bench runs can store their exact parameters (params.json)
python3 - "$LOGDIR/current_server.json" "$CFG" "$MODE" "$CMD" <<'PY'
import json, os, sys
keys = ["CTX","KV","NOMTP","MTPN","PMIN","SPECTYPE","DFLASH","DFLASH_MODEL","DFN","NCMOE","THREADS","BENCH_HW","SPECSAMP","MTPHEAD"]
json.dump({"config": sys.argv[2], "mode": sys.argv[3], "cmd": sys.argv[4],
           "env": {k: os.environ[k] for k in keys if k in os.environ}}, open(sys.argv[1], "w"), indent=1)
PY
tmux new-session -d -s "$SESSION" "$CMD 2>&1 | tee -a $LOG"
for i in $(seq 1 600); do
  if curl -sf "localhost:$PORT/health" >/dev/null 2>&1; then echo "UP after $((i*2))s  gpu_mem=$(gpu_mem_used) MiB"; exit 0; fi
  if ! tmux has-session -t "=$SESSION" 2>/dev/null; then echo "SERVER DIED"; tail -30 "$LOG"; exit 1; fi
  sleep 2
done
echo "TIMEOUT"; tail -30 "$LOG"; exit 1
