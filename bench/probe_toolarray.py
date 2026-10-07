#!/usr/bin/env python3
"""Long-context tool-array correctness probe (gfx1151 HIP corruption, ggml-org/llama.cpp#27579).

  probe_toolarray.py --url URL --tag NAME [--n 4] [--doc long_700]

A ~29k-token document plus 17 tools (read_file first, then 16 placeholders); the model must call read_file.
A nonce comes first in every prompt so no prompt cache can skip the prefill where the corruption happens.
A healthy server passes n/n. Writes runs/<tag>/probe.json.
"""
import argparse, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench import chat, RES, HERE  # noqa: E402

TOOLS = [{"type": "function", "function": {"name": "read_file", "description": "Read a text file from the repository and return its content.",
          "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}}] + \
        [{"type": "function", "function": {"name": f"tool_{i:02d}", "description": f"Placeholder utility number {i}; accepts one string.",
          "parameters": {"type": "object", "properties": {"arg": {"type": "string"}}, "required": ["arg"]}}} for i in range(16)]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=os.environ.get("BENCH_URL", "http://127.0.0.1:8091")); ap.add_argument("--tag", required=True)
    ap.add_argument("--n", type=int, default=4); ap.add_argument("--doc", default="long_700")
    a = ap.parse_args()
    tasks = {t["id"]: t for t in json.load(open(os.path.join(HERE, "tasks.json")))}
    doc = tasks[a.doc]["prompt"].split("Question:")[0]
    rows = []
    for i in range(a.n):
        msg = f"[probe {time.time()}]\n{doc}\nThat was background material only. Task: open the file inventory/config.py with the right tool so you can check the VAT table."
        o = chat(a.url, [{"role": "user", "content": msg}], 2000, think=False, tools=TOOLS)
        calls = o.get("tool_calls") or []
        names = [c.get("function", {}).get("name") for c in calls]
        ok = "read_file" in names and "config.py" in json.dumps([c.get("function", {}).get("arguments") for c in calls])
        rows.append(dict(i=i, ok=ok, names=names, finish=o.get("finish"), err=o.get("error"),
                         prompt_n=(o.get("timings") or {}).get("prompt_n"), content=(o.get("content") or "")[:200]))
        print(rows[-1], flush=True)
    out = os.path.join(RES, a.tag); os.makedirs(out, exist_ok=True)
    s = dict(tag=a.tag, passed=sum(r["ok"] for r in rows), n=len(rows), rows=rows)
    json.dump(s, open(os.path.join(out, "probe.json"), "w"), indent=1)
    print(json.dumps({"probe": f"{s['passed']}/{s['n']}"}))

if __name__ == "__main__":
    main()
