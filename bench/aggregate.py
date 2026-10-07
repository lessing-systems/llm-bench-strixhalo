#!/usr/bin/env python3
"""Aggregate all results into markdown tables."""
import json, os, glob, statistics, sys
from collections import defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# usage: aggregate.py [runs_dir]   (default: $BENCH_OUT or <repo>/results/$BENCH_HW/runs)
RES = sys.argv[1] if len(sys.argv) > 1 else (os.environ.get("BENCH_OUT") or os.path.join(REPO, "results", os.environ.get("BENCH_HW", "unknown-hw"), "runs"))

def load(path):
    try: return json.load(open(path))
    except Exception: return None

def probe(d):
    p = load(os.path.join(d, "probe.json"))
    return f"{p['passed']}/{p['n']}" if p else ""

print("## Speed (tokens/s, single stream; context per run in params.json)\n")
print("| config | prose | code | reasoning | prose@15k | prose@29k | prose@52k | prefill@15k | prefill@52k | VRAM MiB | probe@29k |")
print("|---|---|---|---|---|---|---|---|---|---|---|")
for d in sorted(glob.glob(f"{RES}/*/speed.json")):
    s = load(d)
    if not s or not s.get("summary"): continue
    m = s["summary"]; tag = os.path.basename(os.path.dirname(d))
    g = lambda k: m.get(k, "")
    print(f"| {tag} | {g('prose')} | {g('code')} | {g('reasoning')} | {g('prose@long_350')} | {g('prose@long_700')} | {g('prose@long_1250')} | {g('pp@long_350')} | {g('pp@long_1250')} | {s.get('gpu_mem_mib_after') or s.get('gpu_mem_mib')} | {probe(os.path.dirname(d))} |")

print("\n## Eval suite (58 auto-graded items; code category with repeats)\n")
print("| model | overall (rep 0) | math | logic | knowledge | code (all reps) | instruct | tools | longctx | cap-hit | loops | avg tokens |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|")
for f in sorted(glob.glob(f"{RES}/*/eval.jsonl")):
    tag = os.path.basename(os.path.dirname(f))
    recs = [json.loads(l) for l in open(f)]
    r0 = [r for r in recs if r.get("rep", 0) == 0]
    by = defaultdict(list)
    for r in r0: by[r["cat"]].append(r["ok"])
    code_all = [r["ok"] for r in recs if r["cat"] == "code"]
    c = lambda k: f"{sum(by[k])}/{len(by[k])}" if by[k] else ""
    toks = [r["compl_tok"] for r in r0 if r.get("compl_tok")]
    print(f"| {tag} | {sum(r['ok'] for r in r0)}/{len(r0)} ({100*sum(r['ok'] for r in r0)/len(r0):.0f}%) | {c('math')} | {c('logic')} | {c('knowledge')} | "
          f"{sum(code_all)}/{len(code_all)} | {c('instruct')} | {c('tools')} | {c('longctx')} | "
          f"{sum(1 for r in r0 if r.get('err')=='length')} | {sum(1 for r in r0 if r.get('err')=='loop')} | {round(statistics.mean(toks)) if toks else ''} |")

print("\n## Agentic coding bench (12 tasks x repeats, tool-driven, hidden tests)\n")
print("| config | pass | hard tasks (t9-t12) | tool calls | malformed | avg turns | avg completion tok | avg wall s/task |")
print("|---|---|---|---|---|---|---|---|")
for f in sorted(glob.glob(f"{RES}/agentv2-*/agent.jsonl")):
    tag = os.path.basename(os.path.dirname(f))
    recs = [json.loads(l) for l in open(f)]
    hard = [r for r in recs if r["task"].split("_")[0] in ("t9", "t10", "t11", "t12")]
    print(f"| {tag} | {sum(r['ok'] for r in recs)}/{len(recs)} | {sum(r['ok'] for r in hard)}/{len(hard)} | {sum(r['calls'] for r in recs)} | "
          f"{sum(r['bad_calls'] for r in recs)} | {statistics.mean(r['turns'] for r in recs):.1f} | {statistics.mean(r['compl_tok'] for r in recs):.0f} | "
          f"{statistics.mean(r['wall_s'] for r in recs):.1f} |")
