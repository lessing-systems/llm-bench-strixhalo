# Benchmarking a new hardware stack

Lessons from two hardware stacks (an RTX 4080 SUPER box and this Strix Halo), turned into a procedure. Only the Strix Halo data is published here.

## 0. Name the stack

`<gpu>-<vram>_<cpu>_<os>-<ram>`, lowercase, e.g. `rtx4080super-16gb_i7-13700kf_wsl2-64gb` or `strix-halo-395`.
Everything for that box lives in `profiles/<hw-id>.sh` and `results/<hw-id>/`. Never mix results from different stacks in one directory. Driver, kernel or llama.cpp updates count as the same stack, but note them in `hardware.md` (re-run `scripts/hwinfo.sh`).

## 1. Fingerprint and baseline first

1. `scripts/hwinfo.sh <llama.cpp dir> > results/<hw-id>/hardware.md`
2. Benchmark **what is currently deployed, exactly as deployed** (same binary, same flags), but at the target context size. Users' remembered numbers are often wrong: "45 t/s" measured as 35.
3. Write down the requirements before testing: minimum context, minimum quality (reference model), minimum speed, and which workload matters (here: planning, coding, tool calling, so the agent suite is the tie-breaker).

## 2. Build llama.cpp fresh

`scripts/build-llamacpp.sh cuda|hip|vulkan|cpu <dir>`. Upstream changes weekly (MTP, DFlash, new quant kernels). Keep the old binary for the baseline. Check `--help` for `draft-mtp`, `draft-dflash` and `--lazy-mode`. On AMD, build **both HIP and Vulkan** and benchmark both. Neither is reliably faster; it varies by quant type and model.

## 3. Shortlist models by memory budget

- **Usable fast memory:**
  - discrete GPU: VRAM minus desktop/OS use (Windows took 1.7 GB of 16)
  - unified memory (Strix Halo, Apple): the GPU-visible pool (BIOS UMA + GTT on Linux)
- **Rule of thumb:** weights + KV(ctx) + compute buffers + speculative-draft overhead (MTP ~1.2 GB, DFlash ~1.2 GB plus its own KV) must fit with **≥ 0.4 GB headroom**.
- **Bandwidth decides decode speed.** Decode t/s ≈ bandwidth / bytes read per token.
  - Dense 27B at ~3.5 bpw ≈ 12 GB per token.
  - MoE: only the *active* experts are read per token, e.g. 6B active ≈ 2–3 GB.
  - So on low-bandwidth / big-memory boxes (Strix Halo ~256 GB/s), big sparse MoEs win; on high-bandwidth / small-VRAM cards (4080: 736 GB/s), the best dense model that fits wins.
- **Prefer modern mixed-precision quants** (GSQ-RCO, Unsloth UD, byteshape) over plain K-quants. They were "task-lossless" at 3.5 bpw, which freed room for speculative decoding.
- Read model cards for **license limits** (e.g. Swift: free below US$1M revenue).

## 4. Order of testing (cheap → expensive)

1. **speed** for every candidate config (~5–10 min each). Discard anything below the speed floor.
2. **eval** for survivors (~20–40 min each with 4 slots).
3. **agent** ×3 repeats for the top 2–4 (~20–80 min each).
4. **Tuning sweep** on the winner: speculative depth (`MTPN`, `PMIN`), `SPECTYPE=draft-mtp,ngram-mod`, `-ub`, KV type.
5. Re-run the code category with `--only code --repeat 4` for close calls.

`queues/first-pass.sh` and `queues/tuning-sweep.sh` encode this. Copy them and edit the config names.

## 5. Pitfalls we hit (check for these on every stack)

- **Speculative decoding is workload-dependent.** MTP gave +40% on prose and +90% on code/reasoning; deeper drafts trade prose for code. Measure all three text types.
- **Raw t/s ≠ task throughput.** On the RTX 4080 box, Bonsai decoded 2× faster than Swift but needed 4× the tokens and turns per agentic task: 65 s vs 27 s per task. Rank on agent wall time per task when agents are the workload.
- **tmux `-t NAME` prefix-matches** (`NIGHT` matched `NIGHT2`). Use `=NAME` for exact match, as `serve.sh` does.
- **Shell quoting in queues:** env lists like `"DFLASH=1;DFN=5"` must be quoted.
- **Test hygiene:** hidden tests must not mutate global state (use `monkeypatch`); race-condition tests need several rounds. If you fix a grader, re-grade saved work dirs with `bench/agent/regrade.py <tag>` instead of re-running.
- **Small n:** one eval item is about 1.7 points. Treat 1–2 item differences as noise; use repeats.

## 6. Deliverables per stack

`results/<hw-id>/`:
- `hardware.md`
- `REPORT.md`: recommendation, tables, what failed and why
- `tables.md`: `bench/aggregate.py` output
- `launch/`: the exact server scripts for the top 1–3, plus a parameter table
- `runs/<tag>/`: raw results, each with `params.json`

## Notes for Strix Halo (AMD Ryzen AI Max+ 395, 128 GB unified)

Measured 2026-10-06 (`results/strix-halo-395/REPORT.md`). These replace the first-principles guesses that were here.

- **Check for a model-specific engine first.** For Qwen3.8-Flash-Next, halogen-flash-server (hand-written gfx1151 kernels) decoded ~1.6x faster than llama.cpp (HIP, Vulkan, or the Nathanw Vulkan fork) and prefilled 3-5x faster (1,500-1,650 vs 270-530 t/s at 15-52k). No llama.cpp flag closes that gap. Engines that accept GGUF (halogen's `HALOGEN_CHECKPOINT=<gguf>`) let you swap in a better *model* without losing the fast kernels.
- **A model that thinks less beats raw t/s, again.** Swift-1.5 Flash-Next decoded ~15% slower than base Flash-Next on the same engine, yet finished agentic tasks 25% faster (40 vs 54 s) with 28% fewer tokens and an equal-or-better eval.
- **Memory hygiene before every load (unified memory + ZFS):**
  - `sync; echo 3 > /proc/sys/vm/drop_caches`: the ZFS ARC grew to 43 GB from model reads and counts against MemAvailable. halogen refuses to pin weights under a 16 GiB floor.
  - `echo 1 > /proc/sys/vm/compact_memory`: right after a ~100 GB process exits, free memory is fragmented, and big allocations stall for 10-20+ minutes at 100% of one core with no output (looks like a hang).
  - `serve.sh` (PREP_MEM=1, on in the Strix Halo profile) and `scripts/external_bench.sh` do both.
- **llama.cpp on ZFS: load with `-lm none`.** `-lm mmap` of a 94 GB GGUF was page-fault bound and never finished in 20 min; `-lm none` loads in ~60 s and keeps the Flash-Next n-gram table resident (fits: ~89 GB at 128k).
- **HIP correctness: keep `-b == -ub`.** ROCm 7.2.x on gfx1151 silently corrupts long-context output when `n_ubatch < n_batch` (ggml-org/llama.cpp#27579, fix #27311 unmerged as of 2026-10-06). `bench/probe_toolarray.py` (29k tokens + 17 tools) runs after every speed test to catch this; all configs here passed 4/4.
- **Speculative heads go stale with the engine.** unsloth re-uploaded the Flash-Next MTP heads on 2026-10-05 (same size, new hashes); the old head crashes current llama.cpp at start. Compare LFS oids against local files, not sizes.
- **Warm halogen before measuring.** The first speed run after a start was ~10% slower on prose; discard it.
- **HIP vs Vulkan (llama.cpp, Flash-Next MoE):** within ~10% of each other on decode; Vulkan held up better at 52k (26.6 vs 20.2 t/s). The Nathanw fork's newer bundled RADV raised prefill ~40% but decoded slower.
- **Memory pool:** BIOS UMA was only 2 GB; the GPU pool is GTT (120 GB via `ttm.pages_limit`). Read GPU memory from `/sys/class/drm/card1/device/mem_info_gtt_used`, not `rocm-smi` VRAM.
- **Disk / downloads:** check space with `zfs list` / `zpool list`, not `df`. HF downloads ran at ~65 MB/s unauthenticated.
- **Don't `pkill -f` on a shared box:** a pattern kill matched the tmux server and took every session down. Kill by PID or `tmux kill-session -t =NAME`.
