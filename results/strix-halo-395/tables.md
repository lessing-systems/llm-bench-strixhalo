## Speed (tokens/s, single stream; context per run in params.json)

| config | prose | code | reasoning | prose@15k | prose@29k | prose@52k | prefill@15k | prefill@52k | VRAM MiB | probe@29k |
|---|---|---|---|---|---|---|---|---|---|---|
| fn-iq3s-hip-mtp3 | 27.1 | 40.8 | 42.4 | 25.5 | 24.2 | 20.9 | 338 | 275 | None | 4/4 |
| fn-iq3s-vk-mtp3 | 27.4 | 44.4 | 42.8 | 28.0 | 26.2 | 26.7 | 329 | 259 | None | 4/4 |
| fn-udiq4xs-hip-mtp3 | 25.9 | 41.2 | 38.3 | 25.9 | 23.8 | 20.2 | 336 | 272 | None | 4/4 |
| fn-udiq4xs-hip-nomtp | 21.8 | 21.8 | 21.8 | 19.2 | 16.8 | 13.7 | 345 | 282 | None | 4/4 |
| fn-udiq4xs-nw-mtp3 | 24.6 | 40.5 | 39.6 | 23.3 | 20.7 | 18.7 | 531 | 369 | None | 4/4 |
| fn-udiq4xs-vk-mtp3 | 27.6 | 43.5 | 43.6 | 29.7 | 25.0 | 26.6 | 378 | 284 | None | 4/4 |
| halogen-0.16.2-r2 | 40.6 | 50.0 | 50.3 | 41.0 | 40.9 | 41.1 | 1601 | 1658 | None |  |
| halogen-0.16.2-r3 | 41.7 | 51.3 | 51.6 | 41.6 | 43.5 | 41.2 | 1604 | 1655 | None |  |
| halogen-0.16.2-swift-iq4xs-warmup | 33.9 | 41.6 | 42.5 | 33.5 | 35.1 | 33.6 | 1504 | 1623 | None |  |
| halogen-0.16.2-swift-iq4xs | 36.0 | 43.2 | 40.9 | 34.9 | 34.9 | 36.1 | 1578 | 1634 | None | 4/4 |
| halogen-0.16.2 | 36.6 | 48.2 | 48.4 | 38.4 | 38.8 | 37.8 | 1478 | 1651 | None | 4/4 |
| halogen-baseline | 42.4 | 49.5 | 50.7 | 41.0 | 41.9 | 41.6 | 1430 | 1489 | 11885 | 4/4 |
| swfn-iq3xxs-hip-mtp3 | 27.7 | 44.6 | 43.9 | 27.4 | 23.6 | 21.7 | 412 | 327 | None | 4/4 |
| swfn-iq3xxs-vk-mtp3 | 28.8 | 44.0 | 46.5 | 29.1 | 24.2 | 26.4 | 352 | 275 | 56332 | 4/4 |
| swift27b-iq3s-hip-mtp2 | 22.4 | 30.7 | 31.8 | 22.0 | 18.9 | 15.9 | 283 | 232 | None | 4/4 |

## Eval suite (58 auto-graded items; code category with repeats)

| model | overall (rep 0) | math | logic | knowledge | code (all reps) | instruct | tools | longctx | cap-hit | loops | avg tokens |
|---|---|---|---|---|---|---|---|---|---|---|---|
| halogen-0.16.2-swift-iq4xs | 56/58 (97%) | 11/13 | 8/8 | 12/12 | 10/10 | 8/8 | 4/4 | 3/3 | 0 | 0 | 2004 |
| halogen-baseline | 55/58 (95%) | 11/13 | 8/8 | 11/12 | 10/10 | 8/8 | 4/4 | 3/3 | 0 | 0 | 2212 |

## Agentic coding bench (12 tasks x repeats, tool-driven, hidden tests)

| config | pass | hard tasks (t9-t12) | tool calls | malformed | avg turns | avg completion tok | avg wall s/task |
|---|---|---|---|---|---|---|---|
| agentv2-halogen-0.16.2-swift-iq4xs | 36/36 | 12/12 | 320 | 0 | 6.6 | 1571 | 40.4 |
| agentv2-halogen-0.16.2 | 36/36 | 12/12 | 338 | 2 | 7.0 | 2341 | 53.3 |
| agentv2-halogen-baseline | 36/36 | 12/12 | 323 | 2 | 6.9 | 2193 | 54.2 |
