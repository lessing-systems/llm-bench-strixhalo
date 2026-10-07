#!/usr/bin/env bash
# up.sh: start halogen + Swift-1.5 Flash-Next on :8731 (see docker-compose.yml). Needs passwordless sudo.
#   PULL=1 ./up.sh   pull a prebuilt image from your own registry instead of building it locally
set -eu
cd "$(dirname "$0")"
DC=(sudo docker compose -p halogen-swift -f docker-compose.yml)

if curl -sf localhost:8731/health >/dev/null; then
  echo "something already answers on :8731 (another halogen?); bring it down first"; exit 1
fi
# The ZFS ARC counts against MemAvailable (halogen refuses to pin under 16 GiB free), and a freshly freed
# 100 GB is fragmented: big pinned allocations then stall in compaction for many minutes. Clear both first.
sync; echo 3 | sudo tee /proc/sys/vm/drop_caches >/dev/null; echo 1 | sudo tee /proc/sys/vm/compact_memory >/dev/null
echo "MemAvailable: $(awk '/MemAvailable/{printf "%d", $2/1048576}' /proc/meminfo) GiB"

if [[ ${PULL:-0} == 1 ]]; then "${DC[@]}" pull; else "${DC[@]}" build; fi
"${DC[@]}" up -d
until curl -sf localhost:8731/health >/dev/null; do
  sleep 5
  if "${DC[@]}" ps -a --status exited --format '{{.Name}}' | grep -q .; then
    echo "a container exited:"; "${DC[@]}" logs --tail 15; exit 1; fi
done
curl -s localhost:8731/health | python3 -c 'import json,sys; d=json.load(sys.stdin); print("up:", d["model"], d["version"], "ctx", d["context"], "format", d["checkpoint_format"])'
