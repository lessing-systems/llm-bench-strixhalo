# Launch configs: Strix Halo 395 / 128 GB (2026-10-06)

Every setup here serves the OpenAI API for one 128k-context slot and needs the whole box (one ~110 GB engine at a time).
Only one may hold port 8731 (the benchmark composes use 8732).

| Rank | Directory | Engine | Model / weights | Use for |
|---|---|---|---|---|
| **1** | `swift-halogen/` | halogen-flash-server 0.16.2 (pinned digest), image built locally as `local/halogen-swift:0.16.2-swift1.5-iq4xs` | Swift-1.5 Qwen3.8-Flash-Next **IQ4_XS** GGUF (UkisAI, 97.7 GB, `$MODELS_DIR/swift-flashnext-gguf`) + halogen's MTP head and tokenizer | planning, coding, tool calling (default) |
| 2 | `halogen-0.16.2/` | halogen-flash-server 0.16.2 | halogen's own v2 checkpoint (base Qwen3.8-Flash-Next, `$MODELS_DIR/halogen-qwen38-flash-next`) | fallback without the Swift license; long-context prefill |
| 3 | stock halogen-flash-server 0.15.0 checkout (not included) | halogen-flash-server 0.15.0 | same v2 checkpoint | baseline, rollback |

The images come from `ghcr.io/peonist-ai/halogen-flash-server` (0.15.0 / 0.16.2). `swift-halogen/Dockerfile` is halogen 0.16.2 pinned by digest plus the settings below as `ENV`; nothing in the engine is modified.

```bash
# weights first (see ../README.md, "Get the weights"), then:
launch/swift-halogen/up.sh        # drop caches, compact, build, up, wait for /health
# stop:
sudo docker compose -p halogen-swift -f launch/swift-halogen/docker-compose.yml down
```

## Parameters and why

| Parameter | #1 Swift on halogen | #2/#3 halogen v2 | Why |
|---|---|---|---|
| `HALOGEN_CHECKPOINT` | `/gguf/IQ4_XS/Swift-1.5-…-IQ4_XS-00001-of-00003.gguf` | unset (v2 `.hgn`) | Swift is a GGUF; halogen repacks it losslessly at start (66.9 GiB, ~25 s warm). Every tensor type (IQ4_XS/IQ4_NL/Q8_0/Q5_K/Q6_K/BF16) is on halogen's supported list; checked before downloading. |
| `HALOGEN_MTP_HEAD` | `/models/qwen38-flash-next-mtp.hgn` | (in checkpoint) | a GGUF carries no head halogen can run; base head acceptance on Swift is the same as on base (prose 0.67, code 0.93) |
| `HALOGEN_CTX` / `KV_POOL_POSITIONS` | 131072 | 131072 | requirement: 128k context |
| `HALOGEN_KV_SLOTS` | 1 | 1 | single user; speculative decoding is fastest alone |
| `HALOGEN_MAX_TOK` | 16384 | 16384 | stock 0.15 baseline value; prefill arena size (32768 is ~9% faster prefill but costs ~4 GiB) |
| `HALOGEN_MAX_TOKENS_DEFAULT` / `_CAP` | 8192 / 16384 | same | stock 0.15 baseline value |
| `HALOGEN_HOST_RESERVE_GIB` | 28 | 28 | stock 0.15 baseline value; leaves page cache for the 26.8 GiB (Swift) / 47.7 GiB (v2) lookup table read from disk |
| `HALOGEN_PROMPT_CACHE` | 2 | 2 | resume conversations at any length (agent turns re-use their prefix) |
| `HALOGEN_WEIGHTS_LOCK` | 1 | 1 | pinned weights; required for the measured decode speed |
| drafter | MTP head, depth 2 (default) | same | halogen's tuned default; depth 3 is +7% on code but -5..8% on agent/prose per its docs |
| memory prep before start | `sync; drop_caches; compact_memory` (`up.sh`) | same | the ZFS ARC (up to 43 GB) counts against MemAvailable and halogen refuses to pin under a 16 GiB floor; fragmentation stalls big allocations for minutes |
| client sampling (benchmarked) | temp 1.0, top-p 0.95, top-k 20, `reasoning_effort: medium` | same | Qwen's recommendation; prompt lookup (PLD) only engages for greedy requests, so greedy agent clients will see a little more speed |

## Measured (128k context, single stream)

| | #1 Swift on halogen 0.16.2 | #2 halogen 0.16.2 | #3 halogen 0.15.0 |
|---|---|---|---|
| agentic, 12 tasks × 3 | **36/36, 40.4 s/task**, 1,571 tok/task, 0 malformed | 36/36, 53.3 s/task, 2,341 tok/task | 36/36, 54.2 s/task, 2,193 tok/task |
| eval (58 items) | **56/58** | (same checkpoint as #3) | 55/58 |
| decode prose / code / reasoning | 36.0 / 43.2 / 40.9 | 41.7 / 51.3 / 51.6 | 42.4 / 49.5 / 50.7 |
| decode @52k / prefill @52k | 36.1 / 1,634 | 41.2 / 1,655 | 41.6 / 1,489 |
| RAM pinned | 68.3 GiB (+ lookup table via page cache) | ~62 GiB (+47.7 GiB table via page cache) | same as #2 |

Other files here: `halogen-0.16.2/` and `halogen-0.16.2-swift-iq4xs/` are the benchmark composes (port 8732, project
`halogen-bench`), used by `scripts/external_bench.sh`.
