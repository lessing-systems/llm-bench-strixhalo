# Local LLM shoot-out: Strix Halo (Ryzen AI Max+ 395, Radeon 8060S, 128 GB), 2026-10-06

**Terminology:** "production" / "baseline" = halogen-flash-server 0.15.0 serving Qwen3.8-Flash-Next from halogen's own
checkpoint, i.e. the setup the author was already running before this shoot-out.

**Requirements:** context ≥ 128k, quality ≥ production halogen
(Qwen3.8-Flash-Next), speed matching or beating halogen, ranked by **wall time per solved agentic task**, with
planning, coding and tool calling weighted most.

## TL;DR

| # | Setup | Agentic (12 × 3) | Eval (58) | Decode prose / code / reasoning | Decode @52k | Prefill @52k |
|---|---|---|---|---|---|---|
| **1** | **Swift-1.5 Qwen3.8-Flash-Next IQ4_XS on halogen 0.16.2** | **36/36, 40.4 s/task**, 1,571 tok, 0 malformed | **56/58 (97%)** | 36.0 / 43.2 / 40.9 | 36.1 | 1,634 |
| 2 | halogen 0.16.2, own v2 checkpoint (base Flash-Next) | 36/36, 53.3 s/task, 2,341 tok, 2 malformed | = #ref (same weights) | 41.7 / 51.3 / 51.6 | 41.2 | **1,655** |
| ref | **production**: halogen 0.15.0, v2 checkpoint | 36/36, 54.2 s/task, 2,193 tok, 2 malformed | 55/58 (95%) | **42.4 / 49.5 / 50.7** | **41.6** | 1,489 |
| 3 | best llama.cpp: Vulkan, Swift-1.5 Flash-Next GSQ-RCO IQ3_XXS + new MTP head (n=3) | not run (below speed floor) | not run | 28.8 / 44.0 / 46.5 | 26.4 | 275 |

**Recommendation: #1.** Agentic tasks finish **25% faster** (40.4 vs 54.2 s), at equal or
better quality (eval 56/58 vs 55/58; 36/36 agentic with zero malformed tool calls vs 2). It's the same halogen engine
and the same 128k / 1-slot settings as production, one release newer, serving UkisAI's Swift-1.5 post-train of
Flash-Next, which thinks about 30% less per agentic task. Packaged as a container (`launch/swift-halogen/`, built locally as
`local/halogen-swift:0.16.2-swift1.5-iq4xs`), with 0.15.0 and 0.16.2 as fallbacks.

**What you give up:**
- **Raw decode, ~15%.** Swift runs as a GGUF trunk (66.9 GiB of IQ4_XS/IQ4_NL), which halogen reads more slowly than
  its own v2 checkpoint. The draft head is not the cause: acceptance is identical (prose 0.67, code 0.93).
  - It pays off on agentic work, because Swift writes far fewer tokens on hard tasks (averages over 3 repeats vs
    production): t10 thread-safety 3,204 vs 7,034 tokens (81 vs 204 s), t12 misleading bug report 3,153 vs 4,918
    (79 vs 111 s), and t9 CLI 2,987 vs 3,985 (73 vs 88 s).
  - For long prose generation with few tool turns, plain halogen is ~15% faster.
- **License.** Swift Open License v1.0: free, including commercial use, **below US$1M annual revenue**; above that
  it needs UkisAI's enterprise licence (the same terms as the Swift-27B). #2 (Apache/Qwen
  weights via halogen) is the license-free fallback.

Halogen's own claims checked out:
- "~46 t/s at 32k": measured **41–43 t/s** (sampled at temperature 1.0; the claim is greedy with prompt lookup).
- "~1,580 prefill": measured **1,489** (0.15) and **1,655** (0.16.2) t/s at 52k.

Halogen was serving some real traffic during the baseline (a few 40–50k-token prompts); no contention showed in the
measurements.

## Why #1 wins

Wall time per task is the metric (raw decode t/s alone misranks setups), and it decides here again:

| agentic, 36 runs | completion tokens/task | turns | malformed calls | wall s/task |
|---|---|---|---|---|
| Swift on halogen 0.16.2 | **1,571** | 6.6 | **0** of 320 | **40.4** |
| halogen 0.16.2 (base) | 2,341 | 7.0 | 2 of 338 | 53.3 |
| halogen 0.15.0 (base, production) | 2,193 | 6.9 | 2 of 323 | 54.2 |

- **0.15 → 0.16.2 alone is neutral for agents** (54.2 → 53.3 s): decode is unchanged within noise and the +11%
  prefill barely matters at agent-turn context sizes. The gain comes from Swift.
- **Eval:** Swift 56/58, base 55/58.
  - Both miss the same two hard combinatorics items (both thought to the 16k cap, which halogen closes with an
    "answer room").
  - Swift also got `mcq_7`, which base missed after 14k tokens of thinking.
  - Code 10/10, tools 4/4 and long-context 3/3 for both.
  - One item is about 1.7 points, so call the eval a tie and the agentic suite the decider.
- **Eval tokens:** Swift used 9% fewer on the eval (median identical). Its "63% fewer thinking tokens" is measured at
  `xhigh` effort; we run `medium`, where the saving is smaller on single questions and larger on multi-step agent
  work (−28%).

## What didn't work (and why)

- **llama.cpp, every build, on Flash-Next.** Fresh upstream 6c73b3e (2026-10-06) with native Flash-Next MTP, HIP
  (ROCm 7.2.4, rocWMMA FA) and Vulkan (Mesa 25.2.8), plus the Nathanw strix-halo-llamacpp v0.7.6.1 Vulkan fork
  (bundled newer RADV):
  - **Decode:** 24.6–27.7 t/s prose and 40–44 code (MTP n=3); 18.7–26.7 at 52k.
  - **Prefill:** 260–530 t/s, versus halogen's 1,500–1,650.
  - Without MTP, decode is 21.8 t/s flat (halogen serial is ~37), so the gap is in the base kernels and drafting
    can't close it. This matches community reports. Not viable against halogen.
  - Fixes the runs needed:
    - `-lm none`: mmap loading on ZFS never finished in 20 min.
    - `-b == -ub`: HIP corrupts long context when `n_ubatch < n_batch` on gfx1151/ROCm 7.2 (llama.cpp#27579).
    - A long-context tool-array probe, which every config passed 4/4.
- **ISTA GSQ-RCO IQ3_S (83.6 GB)** and **Swift GSQ-RCO IQ3_XXS (76 GB)**: the best low-bit quality per byte, but they
  use IQ2_S/IQ2_XS/IQ3_XXS/Q2_0 tensors that halogen refuses by design. On llama.cpp they run at the same ~27/44 t/s
  as UD-IQ4_XS: decode here is kernel-bound, not bandwidth-bound, so the smaller files don't help.
  - Swift IQ3_XXS on Vulkan hit `vk::Queue::submit: ErrorDeviceLost` once while loading the MTP head. It was
    transient: the retry loaded and ran fine.
- **The old MTP head** in `~/models/Qwen3.8-UD_IQ4_XS/MTP/` (2026-09-18) **crashes current llama.cpp** at start
  (`GGML_ASSERT(buffer)` in the nextn graph). unsloth re-uploaded the heads on 2026-10-05 "due to upstream changes":
  same size, new hashes. The local copy was stale.
- **Dense Swift-1.5 Qwen3.8-27B IQ3_S + MTP** (winner of a separate RTX 4080 SUPER run), reference only: 22.4 / 30.7 / 31.8 t/s, 15.9 at 52k,
  prefill ~230–280. That's bandwidth-bound at 256 GB/s, as expected; a sparse MoE is the right shape for this box.
- **A 4-bit-trunk requant of Swift**, to win back decode: the Swift IQ4_XS has only 0.46 GB of Q8_0 tensors (k/v,
  shared experts, part of ssm_out), so the requant would save under 1% of bytes per token. Not worth the quality
  risk; dropped.
- **Researched, not run:**
  - **GLM-5.3-Flash**: 320B / 18B active; the smallest GGUF (UD-IQ1_S) is 93 GB. That's 3× Flash-Next's active
    parameters at a destructive quant.
  - **gufo** (kyuz0's Strix engine): an independent same-day comparison measured v0.7.1 below halogen 0.16.2 (39.9 vs
    45.6 decode, 1,060 vs 1,437 prefill at 32k), and it needs the 111 GB UD-Q4_K_XL.
  - **hipfire**: no published Flash-Next weights.
  - **EngramHalo**: superseded by the Nathanw fork, per its own author.

## Operational notes

1. **Start procedure matters on this box** (`launch/swift-halogen/up.sh` does all of it):
   - Drop caches first. The ZFS ARC reached 43 GB from model reads, and halogen refuses to pin the 67 GiB Swift repack
     under a 16 GiB MemAvailable floor; the first start failed exactly that way. Halogen's own `fix-kv-reserve.sh` handles the
     same problem.
   - Compact memory. Right after a ~100 GB process exits, big pinned allocations can stall in compaction for 10–20
     minutes at 100% of one core.
2. **Warm-up:** the first speed run after any halogen start was ~10% slower; all figures above are warm.
3. **Sampling:** benchmarked at Qwen's recommendation (temp 1.0, top-p 0.95, top-k 20, `reasoning_effort: medium`),
   the same as the RTX 4080 SUPER run. Halogen's prompt lookup only engages for greedy requests, so agent clients that send
   temperature 0 will be somewhat faster on both setups.
4. **Don't `pkill -f` on a shared box.** A pattern kill matched the tmux server and took every session down. Kill by PID,
   `tmux kill-session -t =NAME`, and start/stop halogen with `docker compose` in its directory.

## Test suite and method

Suites in `bench/` (see the top-level README), at 128k context, single stream:
- **speed:** prose / code / reasoning, plus prose at 15k / 29k / 52k. The nonce is now at the start of the prompt so
  no server can serve a cached prefix; `cache_n=0` was checked.
- **eval:** 58 items, `--conc 1` for halogen's single slot.
- **agent:** 12 tasks × 3.
- **New:** `bench/probe_toolarray.py` (29k tokens + 17 tools, must call `read_file`; it catches the gfx1151 HIP
  corruption.
- External engines run through `scripts/external_bench.sh` with their compose files; `params.json` records each
  container's image, env, mounts and `/health`.

Full tables: `tables.md`. Launch configs and parameter table: `launch/README.md`. Hardware: `hardware.md`.
Raw runs: `runs/<tag>/`. Per-task agent results: `runs/agentv2-*/agent.jsonl` (full transcripts were not kept).
