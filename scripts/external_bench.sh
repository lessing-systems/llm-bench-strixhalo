#!/usr/bin/env bash
# external_bench.sh <compose-dir> <tag> <suites> [agent-repeats]
#
# Benchmarks a docker-compose served engine (e.g. a halogen variant) that serve.sh can't launch:
# brings the compose project up, waits for /health, records params (scripts/external_params.py), runs the
# suites, then brings it down again. Never touches a running base setup (a halogen-flash-server checkout); uses its own
# project name and port.
#
#   <suites>  comma list of: speed, probe, eval, agent      e.g. speed,probe  or  eval,agent
#   env: EXT_PORT (default 8732), EXT_PROJECT (default halogen-bench), KEEP_UP=1 to leave it running,
#        DROP_CACHES=0 to skip sync+drop_caches before up, BENCH_HW (required), BENCH_PY (default .venv/bin/python)
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(dirname "$HERE")"
CDIR=$(cd "$1" && pwd); TAG=$2; SUITES=$3; REPS=${4:-3}
: "${BENCH_HW:?set BENCH_HW}"
PORT=${EXT_PORT:-8732}; PROJ=${EXT_PROJECT:-halogen-bench}; PY=${BENCH_PY:-$REPO/.venv/bin/python}
URL=http://127.0.0.1:$PORT
cd "$REPO"
log(){ echo "######## $(date +%T) $*"; }
dc(){ sudo -n docker compose -p "$PROJ" -f "$CDIR/docker-compose.yml" "$@"; }

if ! curl -sf "$URL/health" >/dev/null; then
  # ZFS ARC counts against MemAvailable and halogen refuses to pin weights under a 16 GiB floor
  # (halogen's fix-kv-reserve.sh does the same before starting). DROP_CACHES=0 to skip.
  # Then compact: after a large process exits, free memory is fragmented and big pinned allocations can stall
  # for tens of minutes at 100% of one core (halogen docs/FLAGS.md, HALOGEN_FRAG_WARN_BLOCKS).
  [[ ${DROP_CACHES:-1} == 1 ]] && { sync; echo 3 | sudo -n tee /proc/sys/vm/drop_caches >/dev/null
                                    echo 1 | sudo -n tee /proc/sys/vm/compact_memory >/dev/null; }
  log "UP $CDIR (MemAvailable $(awk '/MemAvailable/{printf "%d",$2/1048576}' /proc/meminfo) GiB)"; dc up -d || exit 1
  t0=$(date +%s)
  until curl -sf "$URL/health" >/dev/null; do
    sleep 10
    if (( $(date +%s) - t0 > 1500 )); then log "TIMEOUT"; dc logs --tail 40 engine; dc down; exit 1; fi
    if dc ps --status exited | grep -q engine; then log "ENGINE EXITED"; dc logs --tail 60 engine; dc down; exit 1; fi
  done
  log "HEALTHY after $(( $(date +%s) - t0 ))s  mem_used=$(free -g | awk '/Mem/{print $3}')G"
  dc logs engine 2>&1 | grep -iE 'checkpoint|repack|staged|draft|refus|warn' | tail -15
fi
$PY scripts/external_params.py "$URL" "$CDIR" >/dev/null   # -> logs/current_server.json, picked up by every run below
for s in ${SUITES//,/ }; do
  case $s in
    speed) log SPEED $TAG; $PY -u bench/bench.py speed --url "$URL" --tag "$TAG" --runs 3 | grep -A20 '^{$' | tr -d '\n '; echo ;;
    probe) log PROBE $TAG; $PY -u bench/probe_toolarray.py --url "$URL" --tag "$TAG" --n 4 | tail -1 ;;
    eval)  log EVAL $TAG;  $PY -u bench/bench.py eval --url "$URL" --tag "$TAG" --conc 1 | grep -E '"score"|"cats"' ;;
    agent) log AGENT $TAG; $PY -u bench/agent/agent_bench.py --url "$URL" --tag "agentv2-$TAG" --repeat "$REPS" | tail -1 ;;
    *) log "unknown suite $s" ;;
  esac
done
[[ ${KEEP_UP:-0} == 1 ]] || { log DOWN; dc down; }
log DONE
