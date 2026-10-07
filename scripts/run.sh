#!/usr/bin/env bash
# run.sh <queue-file>
#
# Runs a benchmark queue. A queue file is a bash script that calls these steps:
#
#   speed <config> "<ENV=..;ENV=..>" <tag> ["extra server args"]   # speed suite (single stream) + long-context
#                                                                  # tool-array correctness probe (PROBE=0 to skip)
#   evalr <config> <tag> [bench.py eval args, e.g. --only code --repeat 4]   # eval suite (np=4)
#   agent <config> "<ENV=..;ENV=..>" <tag> <repeats> ["extra server args"]  # agentic coding suite
#
# The quoted ENV list is passed to serve.sh (e.g. "MTPN=2", "NOMTP=1", "DFLASH=1;DFN=5;DFLASH_MODEL=/m/x.gguf").
# Quote it, because ';' is a shell separator.
# Results: results/$BENCH_HW/runs/<tag>/ ; server logs: results/$BENCH_HW/logs/
#
# Example:  BENCH_HW=strix-halo-128gb tmux new -d -s Q "scripts/run.sh queues/first-pass.sh 2>&1 | tee -a q.log"
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(dirname "$HERE")"
: "${BENCH_HW:?set BENCH_HW}"
PY=${BENCH_PY:-python3}
cd "$REPO"
log(){ echo "######## $(date +%T) $*"; }
speed(){ log SPEED "$3"; env $(echo "$2" | tr ';' ' ') scripts/serve.sh "$1" speed ${4:-} || return
          $PY -u bench/bench.py speed --tag "$3" --runs "${SPEED_RUNS:-2}" | grep -A20 '^{$' | tr -d '\n '; echo
          [[ ${PROBE:-1} == 1 ]] && $PY -u bench/probe_toolarray.py --tag "$3" --n "${PROBE_N:-4}" | tail -1; }
evalr(){ local cfg=$1 tag=$2; shift 2; log EVAL "$tag" "$@"; scripts/serve.sh "$cfg" eval \
          && $PY -u bench/bench.py eval --tag "$tag" "$@" | grep -E '"score"|"cats"'; }
agent(){ log AGENT "$3"; env $(echo "$2" | tr ';' ' ') scripts/serve.sh "$1" speed ${5:-} \
          && $PY -u bench/agent/agent_bench.py --tag "$3" --repeat "$4" | tail -1; }
source "$1"
log QUEUE DONE
$PY bench/aggregate.py > "results/$BENCH_HW/tables.md" && log "tables -> results/$BENCH_HW/tables.md"
