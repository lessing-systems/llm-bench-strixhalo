#!/usr/bin/env python3
"""LLM test suite runner for llama-server (OpenAI-compatible API).

  bench.py eval  --url http://127.0.0.1:8091 --tag NAME [--conc 4] [--only cat1,cat2] [--repeat 1]
  bench.py speed --url http://127.0.0.1:8091 --tag NAME [--runs 3] [--no-long]

Results -> $BENCH_OUT/<tag>/ or <repo>/results/$BENCH_HW/runs/<tag>/ {eval.jsonl,eval_summary.json,speed.json}
"""
import argparse, json, os, re, subprocess, sys, tempfile, threading, time, statistics
from concurrent.futures import ThreadPoolExecutor
import requests
from params import write_params

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Results root: $BENCH_OUT, else <repo>/results/$BENCH_HW/runs (see docs/GUIDELINES.md)
RES = os.environ.get("BENCH_OUT") or os.path.join(REPO, "results", os.environ.get("BENCH_HW", "unknown-hw"), "runs")

SAMPLING = dict(temperature=1.0, top_p=0.95, top_k=20, min_p=0.0, presence_penalty=0.0)
THINK = {"enable_thinking": True, "preserve_thinking": False, "reasoning_effort": "medium"}
NOTHINK = {"enable_thinking": False}


def chat(url, messages, max_tokens, think=True, tools=None, timeout=3600, extra=None):
    body = dict(messages=messages, max_tokens=max_tokens, stream=False, **SAMPLING)
    body["chat_template_kwargs"] = THINK if think else NOTHINK
    if tools: body["tools"] = tools
    if extra: body.update(extra)
    t0 = time.time()
    r = requests.post(url + "/v1/chat/completions", json=body, timeout=timeout)
    wall = time.time() - t0
    if r.status_code != 200:
        return dict(error=f"HTTP {r.status_code}: {r.text[:300]}", wall=wall)
    j = r.json()
    ch = j["choices"][0]; msg = ch["message"]
    return dict(content=msg.get("content") or "", reasoning=msg.get("reasoning_content") or "",
                tool_calls=msg.get("tool_calls") or [], finish=ch.get("finish_reason"),
                usage=j.get("usage", {}), timings=j.get("timings", {}), wall=wall, raw_msg=msg)


# ------------------------------------------------------------------ graders
def final_answer(text):
    m = re.findall(r"ANSWER:\s*(.+)", text)
    if not m: return None
    a = m[-1].strip().strip("*").strip()
    a = re.sub(r"^\\boxed\{(.*)\}$", r"\1", a).strip("*` ").rstrip(".")
    return a

def g_int(t, out):
    a = final_answer(out["content"])
    if a is None: return False, "no ANSWER line"
    nums = re.findall(r"-?\d[\d,]*", a)
    if not nums: return False, f"no int in {a!r}"
    v = int(nums[0].replace(",", ""))
    return v == t["answer"], f"got {v} want {t['answer']}"

def norm(s): return re.sub(r"\s+", " ", s.lower().replace("*", "").strip())

def g_exact_ci(t, out):
    a = final_answer(out["content"])
    if a is None: return False, "no ANSWER line"
    return norm(a) == norm(t["answer"]), f"got {a!r} want {t['answer']!r}"

def g_set_ci(t, out):
    a = final_answer(out["content"])
    if a is None: return False, "no ANSWER line"
    got = {x.strip().lower() for x in re.split(r"[,;]| and ", a) if x.strip()}
    want = {x.strip().lower() for x in t["answer"].split(",")}
    return got == want, f"got {sorted(got)} want {sorted(want)}"

def g_letter(t, out):
    a = final_answer(out["content"])
    if a is None: return False, "no ANSWER line"
    m = re.match(r"\(?([A-D])\b", a.strip())
    return bool(m) and m.group(1) == t["answer"], f"got {a!r} want {t['answer']}"

def extract_code(text):
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text, re.S)
    return max(blocks, key=len) if blocks else text

def g_python(t, out):
    code = extract_code(out["content"])
    src = code + "\n\n# ---- tests\n" + t["tests"] + "\nprint('ALL_TESTS_PASSED')\n"
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(src); fn = f.name
    try:
        p = subprocess.run([sys.executable, fn], capture_output=True, text=True, timeout=60)
        ok = "ALL_TESTS_PASSED" in p.stdout
        return ok, ("ok" if ok else (p.stderr.strip().splitlines() or ["?"])[-1][:200])
    except subprocess.TimeoutExpired:
        return False, "timeout"
    finally:
        os.unlink(fn)

def words(s): return re.findall(r"[A-Za-zÀ-ÿ0-9'’-]+", s)

def g_ifeval(t, out):
    c = out["content"].strip(); k = t["checks"]; fails = []
    if k.get("no_comma") and "," in c: fails.append("comma")
    if "words" in k:
        n = len(words(c));
        if not (k["words"][0] <= n <= k["words"][1]): fails.append(f"words={n}")
    if "max_words" in k and len(words(c)) > k["max_words"]: fails.append(f"words={len(words(c))}")
    if "bullets" in k:
        lines = [l for l in c.splitlines() if l.strip()]
        b = [l for l in lines if l.startswith("- ")]
        if len(b) != k["bullets"]: fails.append(f"bullets={len(b)}")
        if k.get("only_bullets") and len(b) != len(lines): fails.append("extra lines")
    if k.get("json_book"):
        try:
            j = json.loads(c)
            assert isinstance(j["title"], str)
            assert isinstance(j["year"], int) and 1900 <= j["year"] <= 2000
            assert isinstance(j["authors"], list) and len(j["authors"]) == 2 and all(isinstance(x, str) for x in j["authors"])
            assert isinstance(j["rating"], (int, float)) and 0 <= j["rating"] <= 5
            assert isinstance(j["tags"], list) and len(j["tags"]) == 3 and all(isinstance(x, str) and x == x.lower() for x in j["tags"])
        except Exception as e: fails.append(f"json:{type(e).__name__}")
    if k.get("lowercase") and c != c.lower(): fails.append("uppercase")
    if "ends" in k and not c.endswith(k["ends"]): fails.append("ending")
    if "paragraphs" in k:
        n = len([p for p in re.split(r"\n\s*\n", c) if p.strip()])
        if n != k["paragraphs"]: fails.append(f"paras={n}")
    if k.get("title"):
        lines = [l for l in c.splitlines() if l.strip()]
        if not lines or not re.fullmatch(r"<<[^<>]+>>", lines[0].strip()): fails.append("title")
        elif len(lines) - 1 != k["lines_after_title"]: fails.append(f"lines={len(lines)-1}")
    if "word_count_exact" in k:
        w, n = k["word_count_exact"]; got = len(re.findall(rf"\b{w}\b", c, re.I))
        if got != n: fails.append(f"{w}={got}")
    if "no_letter" in k and k["no_letter"] in c.lower(): fails.append("letter")
    if "sentences" in k:
        n = len([s for s in re.split(r"(?<=[.!?])\s+", c) if s.strip()])
        if n != k["sentences"]: fails.append(f"sent={n}")
    if "contains" in k and k["contains"] not in c: fails.append("missing kw")
    if k.get("german") and not re.search(r"\b(der|die|das|ist|und)\b", c): fails.append("not german")
    if "headers" in k:
        hs = [l.strip() for l in c.splitlines() if l.startswith("#")]
        if hs != k["headers"]: fails.append(f"headers={hs}")
    if "numbered" in k:
        tail = c.split("## Action Items")[-1]
        nums = re.findall(r"^\s*(\d+)\.", tail, re.M)
        if nums != [str(i + 1) for i in range(k["numbered"])]: fails.append(f"numbered={nums}")
    return not fails, ",".join(fails) or "ok"

def _args(tc):
    try: return json.loads(tc["function"]["arguments"]) if isinstance(tc["function"]["arguments"], str) else tc["function"]["arguments"]
    except Exception: return None

def g_tool(t, out, url=None):
    exp = t["expect"]; calls = out["tool_calls"]
    if not exp["calls"]:
        if calls: return False, f"unexpected tool call {calls[0]['function']['name']}"
        return exp["content_contains"] in out["content"], "content"
    if len(calls) != len(exp["calls"]): return False, f"{len(calls)} calls, want {len(exp['calls'])}"
    got = []
    for tc in calls:
        a = _args(tc)
        if a is None: return False, "malformed JSON args"
        got.append((tc["function"]["name"], {k: (v.lower() if isinstance(v, str) else v) for k, v in a.items()}))
    for e in exp["calls"]:
        ok = False
        for name, a in got:
            if name != e["name"]: continue
            ea = e["args"]; good = True
            for k, v in ea.items():
                if k == "path_contains": good &= v in str(a.get("path", "")) + str(a.get("pattern", ""))
                elif k == "pattern_contains": good &= v in str(a.get("pattern", ""))
                elif k in ("from", "to"): good &= str(a.get(k, "")).lower() == v
                elif k == "city": good &= v in str(a.get(k, "")).lower()
                else: good &= a.get(k) == v or (isinstance(v, (int, float)) and isinstance(a.get(k), (int, float)) and float(a.get(k)) == float(v))
            if good: ok = True
        if not ok: return False, f"no matching call for {e} in {got}"
    if "followup" in exp and url:
        f = exp["followup"]
        msgs = [{"role": "user", "content": t["prompt"]}, out["raw_msg"]] + \
               [{"role": "tool", "tool_call_id": tc.get("id", "call_0"), "content": f["result"]} for tc in calls]
        msgs[1] = {k: v for k, v in msgs[1].items() if k in ("role", "content", "tool_calls")}
        o2 = chat(url, msgs, 4000, tools=t["tools"])
        out["followup"] = {k: o2.get(k) for k in ("content", "finish", "error")}
        if o2.get("error"): return False, "followup http error"
        if f["content_contains"] not in o2["content"]: return False, "followup content"
    return True, "ok"

GRADERS = dict(int=g_int, exact_ci=g_exact_ci, set_ci=g_set_ci, letter=g_letter, python_tests=g_python, ifeval=g_ifeval)


def loop_detect(text, n=40):
    """Crude repetition detector: same 40-char chunk repeated >= 8 times in the last 4000 chars."""
    tail = text[-4000:]
    if len(tail) < 1000: return False
    from collections import Counter
    cnt = Counter(tail[i:i + n] for i in range(0, len(tail) - n, 7))
    return cnt.most_common(1)[0][1] >= 8


def run_task(url, t, ctx):
    is_long = t["cat"] == "longctx"
    max_tok = 12000 if is_long else 16000
    try:
        out = chat(url, [{"role": "user", "content": t["prompt"]}], max_tok, tools=t.get("tools"))
    except Exception as e:
        out = dict(error=f"{type(e).__name__}: {e}")
    rec = dict(id=t["id"], cat=t["cat"])
    if out.get("error"):
        rec.update(ok=False, why=out["error"], err="http"); return rec, out
    if t["grader"] == "tool": ok, why = g_tool(t, out, url)
    else: ok, why = GRADERS[t["grader"]](t, out)
    err = None
    if out["finish"] == "length": err = "length"
    elif loop_detect(out["reasoning"] + out["content"]): err = "loop"
    elif not out["content"].strip() and not out["tool_calls"]: err = "empty"
    u = out["usage"]; tm = out["timings"]
    rec.update(ok=bool(ok), why=why, err=err, finish=out["finish"], prompt_tok=u.get("prompt_tokens"),
               compl_tok=u.get("completion_tokens"), reason_chars=len(out["reasoning"]), wall=round(out["wall"], 1),
               tg=tm.get("predicted_per_second"), pp=tm.get("prompt_per_second"))
    return rec, out


def cmd_eval(a):
    tasks = json.load(open(os.path.join(HERE, "tasks.json")))
    if a.only: tasks = [t for t in tasks if t["cat"] in a.only.split(",") or t["id"] in a.only.split(",")]
    outdir = os.path.join(RES, a.tag); os.makedirs(outdir, exist_ok=True)
    write_params(outdir, a.url, dict(suite="eval", sampling=SAMPLING, chat_template_kwargs=THINK, max_tokens=16000, max_tokens_longctx=12000, concurrency=a.conc, repeat=a.repeat, only=a.only))
    fn = os.path.join(outdir, "eval.jsonl"); fraw = os.path.join(outdir, "eval_raw.jsonl")
    done = set()
    if os.path.exists(fn) and not a.fresh:
        done = {(json.loads(l)["id"], json.loads(l).get("rep", 0)) for l in open(fn)}
    lock = threading.Lock()
    jobs = [(t, r) for r in range(a.repeat) for t in tasks if (t["id"], r) not in done]
    short = [j for j in jobs if j[0]["cat"] != "longctx"]; long_ = [j for j in jobs if j[0]["cat"] == "longctx"]
    t0 = time.time()
    def work(job):
        t, r = job
        rec, out = run_task(a.url, t, None); rec["rep"] = r
        with lock:
            with open(fn, "a") as f: f.write(json.dumps(rec) + "\n")
            with open(fraw, "a") as f: f.write(json.dumps(dict(id=t["id"], rep=r, **{k: out.get(k) for k in ("content", "reasoning", "tool_calls", "finish", "error", "followup")})) + "\n")
            print(f"[{time.time()-t0:6.0f}s] {rec['id']:22s} {'PASS' if rec['ok'] else 'FAIL'} {rec.get('err') or ''} {rec['why'][:80]} tok={rec.get('compl_tok')}", flush=True)
    with ThreadPoolExecutor(a.conc) as ex: list(ex.map(work, short))
    for j in long_: work(j)  # long-context sequentially (shared KV)
    summarize(a.tag)


def summarize(tag):
    outdir = os.path.join(RES, tag)
    recs = [json.loads(l) for l in open(os.path.join(outdir, "eval.jsonl"))]
    from collections import defaultdict
    by = defaultdict(list)
    for r in recs: by[r["cat"]].append(r)
    s = {"tag": tag, "n": len(recs), "score": round(sum(r["ok"] for r in recs) / len(recs), 3),
         "errors": {e: sum(1 for r in recs if r.get("err") == e) for e in ("http", "length", "loop", "empty")},
         "avg_compl_tok": round(statistics.mean([r["compl_tok"] for r in recs if r.get("compl_tok")] or [0])),
         "cats": {c: f"{sum(r['ok'] for r in v)}/{len(v)}" for c, v in sorted(by.items())}}
    json.dump(s, open(os.path.join(outdir, "eval_summary.json"), "w"), indent=1)
    print(json.dumps(s, indent=1))


# ------------------------------------------------------------------ speed
PROSE = "Write a vivid ~900 word short story about an old lighthouse keeper who discovers that the lighthouse's lamp has been signalling to someone across the sea. Plain prose, no title."
CODEP = "Write a complete, well-commented Python module implementing a thread-safe token-bucket rate limiter class with async support, plus a small CLI demo using argparse. Output only code."
REASON = "A farmer has chickens and cows. There are 50 heads and 140 legs. Then he buys some goats so that the total number of legs becomes 200 and heads 65. How many goats did he buy, and is the problem consistent? Explain step by step."

def gpu_mem():
    """GPU memory in use (MiB). Override with $BENCH_GPU_MEM_CMD (a shell command printing one integer, MiB)."""
    cmd = os.environ.get("BENCH_GPU_MEM_CMD") or ("nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null"
           " || awk '{s+=$1} END {if (NR) printf \"%d\\n\", s/1048576}' /sys/class/drm/card*/device/mem_info_gtt_used")  # AMD APU: GTT
    try: return int(float(subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode().split()[0]))
    except Exception: return None

def cmd_speed(a):
    outdir = os.path.join(RES, a.tag); os.makedirs(outdir, exist_ok=True)
    write_params(outdir, a.url, dict(suite="speed", sampling=SAMPLING, runs=a.runs, long=not a.no_long, max_tokens={"prose": 1000, "code": 1000, "reasoning": 1500, "long": 600}, thinking={"prose": False, "code": False, "reasoning": True, "long": False}))
    tasks = {t["id"]: t for t in json.load(open(os.path.join(HERE, "tasks.json")))}
    tests = [("prose", PROSE, False, 1000), ("code", CODEP, False, 1000), ("reasoning", REASON, True, 1500)]
    res = {"tag": a.tag, "gpu_mem_mib": gpu_mem(), "runs": []}
    # warmup
    chat(a.url, [{"role": "user", "content": "Say hi."}], 16, think=False)
    for name, p, think, mt in tests:
        for r in range(a.runs):
            o = chat(a.url, [{"role": "user", "content": p + f" (variant {r})"}], mt, think=think)
            tm = o.get("timings", {})
            row = dict(test=name, run=r, tg=tm.get("predicted_per_second"), n=tm.get("predicted_n"), pp=tm.get("prompt_per_second"),
                       draft_n=tm.get("draft_n"), draft_acc=tm.get("draft_n_accepted"), err=o.get("error"))
            res["runs"].append(row); print(row, flush=True)
    if not a.no_long:
        for tid in ["long_350", "long_700", "long_1250"]:
            t = tasks[tid]
            doc = t["prompt"].split("Question:")[0]
            # nonce FIRST: servers with a cross-request prompt cache (llama-server slots, halogen) must not reuse a prefix
            msg = f"[run {time.time()}]\n" + doc + "Question: In flowing prose (no lists), describe the overall picture this HR export paints: which departments and offices appear, rough salary ranges, and anything notable. About 400 words."
            o = chat(a.url, [{"role": "user", "content": msg}], 600, think=False)
            tm = o.get("timings", {})
            row = dict(test=f"prose@{tid}", tg=tm.get("predicted_per_second"), n=tm.get("predicted_n"), pp=tm.get("prompt_per_second"),
                       prompt_n=tm.get("prompt_n"), cache_n=tm.get("cache_n"), draft_n=tm.get("draft_n"), draft_acc=tm.get("draft_n_accepted"), err=o.get("error"))
            res["runs"].append(row); print(row, flush=True)
    res["gpu_mem_mib_after"] = gpu_mem()
    agg = {}
    for name in ["prose", "code", "reasoning"]:
        v = [r["tg"] for r in res["runs"] if r["test"] == name and r["tg"]]
        if v: agg[name] = round(statistics.median(v), 1)
    for r in res["runs"]:
        if r["test"].startswith("prose@") and r["tg"]:
            agg[r["test"]] = round(r["tg"], 1); agg["pp@" + r["test"][6:]] = round(r["pp"] or 0)
    res["summary"] = agg
    json.dump(res, open(os.path.join(outdir, "speed.json"), "w"), indent=1)
    print(json.dumps(agg, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["eval", "speed", "summary"])
    ap.add_argument("--url", default=os.environ.get("BENCH_URL", "http://127.0.0.1:8091"))
    ap.add_argument("--tag", required=True)
    ap.add_argument("--conc", type=int, default=4)
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--only", default="")
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--no-long", action="store_true")
    a = ap.parse_args()
    {"eval": cmd_eval, "speed": cmd_speed, "summary": lambda a: summarize(a.tag)}[a.mode](a)
