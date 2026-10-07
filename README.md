# llm-bench-strixhalo

Benchmark data and tooling for choosing a **local LLM serving setup on AMD Strix Halo** (Ryzen AI Max+ 395, Radeon 8060S / gfx1151,
128 GB unified memory), measured 2026-10-06 on Ubuntu 24.04 / kernel 7.0 / ROCm 7.2.4 / Mesa RADV 25.2.8.

The question: *which engine + model + quant gives the best intelligence per second for agentic coding, planning and tool
calling, at 128k context, on one 128 GB box?* Everything here is raw data plus the harness that produced it, so you can
re-run it on your own Strix Halo (or any other OpenAI-compatible server).

## Result

| # | Setup | Agentic (12 tasks × 3) | Eval (58 items) | Decode prose / code / reasoning (t/s) | Decode @52k | Prefill @52k (t/s) |
|---|---|---|---|---|---|---|
| **1** | **Swift-1.5 Qwen3.8-Flash-Next IQ4_XS on halogen-flash-server 0.16.2** | **36/36, 40.4 s/task**, 0 malformed tool calls | **56/58** | 36.0 / 43.2 / 40.9 | 36.1 | 1,634 |
| 2 | halogen 0.16.2, base Flash-Next (own checkpoint) | 36/36, 53.3 s/task | same weights as baseline | 41.7 / 51.3 / 51.6 | 41.2 | 1,655 |
| baseline | halogen 0.15.0, base Flash-Next | 36/36, 54.2 s/task | 55/58 | 42.4 / 49.5 / 50.7 | 41.6 | 1,489 |
| 3 | best llama.cpp (Vulkan, Swift Flash-Next IQ3_XXS + MTP n=3) | not run (below speed floor) | not run | 28.8 / 44.0 / 46.5 | 26.4 | 275 |

Takeaways (details and caveats in [results/strix-halo-395/REPORT.md](results/strix-halo-395/REPORT.md)):

1. **A model-specific engine beats llama.cpp by a wide margin on this chip.** halogen (hand-written gfx1151 kernels) decodes ~1.6× faster than
   llama.cpp (HIP, Vulkan or the Nathanw Vulkan fork) and prefills 3-5× faster (1,500-1,650 vs 260-530 t/s). No llama.cpp flag closed the gap.
2. **A model that thinks less beats raw t/s.** Swift-1.5 decodes ~15% slower than base Flash-Next on the same engine but finishes agentic
   tasks 25% faster (40 vs 54 s), with 28% fewer tokens and equal-or-better eval. Rank on wall time per solved task, not t/s.
3. **The bottleneck is kernels, not bandwidth.** Smaller quants (IQ3) did not speed up llama.cpp decode; a dense 27B is bandwidth-bound at ~22 t/s. Big sparse MoEs fit this box.
4. **Operational pitfalls cost more time than flags** (unified memory + ZFS ARC, memory compaction stalls, a silent HIP corruption bug, stale
   MTP heads). All are listed in the report and in [docs/GUIDELINES.md](docs/GUIDELINES.md).

Caveats: one box, one day, single stream, sampled at temperature 1.0 (Qwen's recommendation), `reasoning_effort: medium`. One eval item ≈ 1.7 points,
so treat 1-2 item differences as noise. The Swift model is free only below US$1M annual revenue (Swift Open License v1.0).

## What is where

```
results/strix-halo-395/
  REPORT.md      the full write-up: recommendation, what failed and why, operational notes
  tables.md      speed / eval / agent tables (bench/aggregate.py output)
  hardware.md    hardware and software fingerprint
  runs/<tag>/    raw results per run: params.json (exact server command or compose file, request settings,
                 bench commit), speed.json, probe.json, eval*.jsonl, agent.jsonl (per-task metrics and final answer), *_summary.json
bench/           the harness (below)
scripts/         serve.sh (profile-driven llama-server launcher), run.sh (queue runner), external_bench.sh (docker-compose engines),
                 download-models.sh (every tested model, skips what is present), build-llamacpp.sh, hwinfo.sh
profiles/        strix-halo-395.sh (all llama.cpp configs measured here) and TEMPLATE.sh for your hardware
queues/          strix-halo-llamacpp.sh, strix-halo-halogen.sh (the exact runs), tuning-sweep.sh
launch/          docker-compose files + Dockerfile for the halogen setups (swift-halogen/ is the winner), with a parameter table
docs/GUIDELINES.md   how to benchmark a new hardware stack, and the pitfalls
```

## The benchmark suites

All three talk to any OpenAI-compatible server (`--url`, default `http://localhost:8091`).

| Suite | Measures | Command |
|---|---|---|
| **speed** | single-stream decode t/s for prose / code / reasoning, plus decode and prefill at 15k / 29k / 52k context. The prompt starts with a nonce so no server can serve a cached prefix | `bench/bench.py speed` |
| **eval** | 58 auto-graded items: procedurally generated math and logic (contamination-proof), MCQ science, 10 coding tasks with hidden tests, IFEval-style constraints, tool calls, long-context aggregation. Also counts token-cap hits, loops, HTTP errors | `bench/bench.py eval` |
| **agent** | 12 agentic coding tasks in a sandbox repo, driven only by tool calls (list/read/write/edit/grep/run_tests), graded by hidden pytest tests. Reports pass rate, malformed tool calls, turns, tokens and **wall time per task** | `bench/agent/agent_bench.py` |
| **probe** | 29k-token prompt + 17 tools; the model must call `read_file`. Catches the gfx1151 HIP long-context corruption | `bench/probe_toolarray.py` |

## Replicate

Needs Python 3.10+, `tmux`, `curl`, and for the winner: Docker with Compose, passwordless `sudo`, ~110 GB free RAM, ~100 GB disk.

```bash
pip install -r requirements.txt
export BENCH_HW=strix-halo-395                      # selects profiles/$BENCH_HW.sh and results/$BENCH_HW/
scripts/hwinfo.sh ~/llama.cpp-bench > results/$BENCH_HW/hardware.md   # your own fingerprint (llama.cpp dir optional)
```

### A. The winner (halogen + Swift-1.5 Flash-Next)

```bash
# Get the weights (not in this repo; ~100 GB). HF_TOKEN speeds it up.
export MODELS_DIR=$HOME/models
scripts/download-models.sh swift-halogen

# Serve it on :8731 (does the memory prep that matters on this box, see below), then benchmark
launch/swift-halogen/up.sh
python3 bench/bench.py speed --url http://127.0.0.1:8731 --tag my-swift-halogen
python3 bench/probe_toolarray.py --url http://127.0.0.1:8731 --tag my-swift-halogen
python3 bench/bench.py eval  --url http://127.0.0.1:8731 --tag my-swift-halogen --conc 1      # halogen has 1 slot
python3 bench/agent/agent_bench.py --url http://127.0.0.1:8731 --tag agentv2-my-swift-halogen --repeat 3
python3 bench/aggregate.py > results/$BENCH_HW/tables.md
```

The `video`/`render` group ids in the compose files (`group_add: ["44", "992"]`) are host-specific: check `getent group video render`.
To reproduce the full halogen comparison unattended (base 0.16.2 and Swift, one compose project at a time): `queues/strix-halo-halogen.sh`.

### B. The llama.cpp comparison

```bash
scripts/build-llamacpp.sh hip    ~/llama.cpp-bench      # ROCm, gfx1151, rocWMMA flash attention
scripts/build-llamacpp.sh vulkan ~/llama.cpp-vulkan     # needs Mesa RADV; paths are read from profiles/strix-halo-395.sh
scripts/download-models.sh llamacpp dense-ref    # ~270 GB; the GGUFs profiles/strix-halo-395.sh points at

tmux new -d -s Q "scripts/run.sh queues/strix-halo-llamacpp.sh 2>&1 | tee -a results/$BENCH_HW/queue.log"
```

Use `scripts/serve.sh <config> speed|eval` to start a single config by hand (llama-server in a tmux session, port 8091).
For another machine, copy `profiles/TEMPLATE.sh` to `profiles/<your-hw-id>.sh`, export `BENCH_HW=<your-hw-id>`, and follow [docs/GUIDELINES.md](docs/GUIDELINES.md).

`scripts/download-models.sh` with no argument fetches every model tested (~490 GB; groups `swift-halogen`, `halogen-base`, `llamacpp`, `dense-ref`).
`DRY_RUN=1` lists what is present and what would be downloaded; `VERIFY=1` checks sha256 against Hugging Face.

### Strix Halo setup notes you will need

- **GPU memory pool:** BIOS UMA was 2 GB; the pool is GTT (~120 GB via `ttm.pages_limit=31457280`, a modprobe option). The profile reads GPU memory from
  `/sys/class/drm/card1/device/mem_info_gtt_used`; set `GPU_CARD=card0` if your card has another index.
- **Before every load:** `sync; echo 3 > /proc/sys/vm/drop_caches; echo 1 > /proc/sys/vm/compact_memory`. A big file cache (ZFS ARC reached 43 GB here) makes
  halogen refuse to pin weights, and fragmented memory after a ~100 GB process exits can stall allocations for 10-20 minutes with no output.
  `scripts/serve.sh`, `external_bench.sh` and `launch/swift-halogen/up.sh` do this for you (they need passwordless `sudo`).
- **llama.cpp:** keep `-b == -ub` on HIP/gfx1151 (silent long-context corruption otherwise, ggml-org/llama.cpp#27579); use `-lm none` if mmap loading from your filesystem is slow.
- **Warm up** any halogen start before measuring: the first speed run was ~10% slower.

## Provenance and limits

- Numbers are from this exact harness at the commit recorded in each `runs/<tag>/params.json`. `params.json` files record the server command or compose file used;
  host paths were rewritten to `~` for publication and nothing else in the data was altered.
- Per-task agent results (`agent.jsonl`: turns, tokens, timings, pass/fail, the model's final summary; not full transcripts) and raw eval outputs are included so every score can be audited.
- Model weights, llama.cpp builds and the third-party engines (halogen-flash-server, Nathanw1014/strix-halo-llamacpp) are not part of this repository and keep their own licenses.

## License

Apache License 2.0, see [LICENSE](LICENSE). Applies to the harness, scripts, configs and benchmark data in this repository; models and third-party engines keep their own licenses.
