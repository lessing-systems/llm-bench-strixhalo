#!/usr/bin/env bash
# The halogen runs behind the winner. halogen is served by docker compose, so this is NOT a run.sh queue; it calls
# scripts/external_bench.sh directly (one compose project at a time, ~110 GB each). Needs passwordless sudo.
#   BENCH_HW=strix-halo-395 queues/strix-halo-halogen.sh
set -eu
cd "$(dirname "$0")/.."
: "${BENCH_HW:?set BENCH_HW}"
# base Flash-Next on halogen 0.16.2 (halogen's own checkpoint)
scripts/external_bench.sh launch/halogen-0.16.2 halogen-0.16.2 speed,probe
scripts/external_bench.sh launch/halogen-0.16.2 halogen-0.16.2 agent 3
# Swift-1.5 Flash-Next IQ4_XS GGUF on halogen 0.16.2 (the winner): warm-up run first, discard it
scripts/external_bench.sh launch/halogen-0.16.2-swift-iq4xs halogen-0.16.2-swift-iq4xs-warmup speed
scripts/external_bench.sh launch/halogen-0.16.2-swift-iq4xs halogen-0.16.2-swift-iq4xs speed,probe,eval
scripts/external_bench.sh launch/halogen-0.16.2-swift-iq4xs halogen-0.16.2-swift-iq4xs agent 3
python3 bench/aggregate.py > "results/$BENCH_HW/tables.md"
