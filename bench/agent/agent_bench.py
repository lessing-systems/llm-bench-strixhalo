#!/usr/bin/env python3
"""Agentic coding benchmark: model drives tools in a sandbox copy of a small repo.

  agent_bench.py --url http://127.0.0.1:8091 --tag NAME [--only t1,t2] [--repeat 1]

Measures: task success (hidden tests), turns, tool-call validity, tokens, wall time.
"""
import argparse, hashlib, json, os, re, shutil, subprocess, sys, tempfile, time
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from params import write_params  # noqa: E402
FIX = os.path.join(HERE, "fixtures", "inventory")
REPO = os.path.dirname(os.path.dirname(HERE))
RES = os.environ.get("BENCH_OUT") or os.path.join(REPO, "results", os.environ.get("BENCH_HW", "unknown-hw"), "runs")
PY = sys.executable  # must have pytest installed

SYSTEM = """You are an autonomous coding agent working inside a Python repository (the current working directory).
You can only interact with the repository through the provided tools. Plan your approach, inspect the relevant files before editing, make minimal correct changes, and verify your work with run_tests.
When you are completely finished, reply with a short summary of what you did and do NOT call any more tools."""

TOOLS = [
 {"type": "function", "function": {"name": "list_files", "description": "List all files in the repository (recursively), relative paths.",
  "parameters": {"type": "object", "properties": {}, "required": []}}},
 {"type": "function", "function": {"name": "read_file", "description": "Read a text file. Returns the content with line numbers.",
  "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
 {"type": "function", "function": {"name": "write_file", "description": "Create or overwrite a file with the given full content.",
  "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
 {"type": "function", "function": {"name": "edit_file", "description": "Replace an exact, unique snippet of text in a file with new text.",
  "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old": {"type": "string", "description": "exact existing text, must occur exactly once"}, "new": {"type": "string"}}, "required": ["path", "old", "new"]}}},
 {"type": "function", "function": {"name": "grep", "description": "Search the repository for a regular expression. Returns matching lines as path:line:text.",
  "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}}, "required": ["pattern"]}}},
 {"type": "function", "function": {"name": "run_tests", "description": "Run the test suite with pytest (optionally a single test file) and return the output.",
  "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "optional test file path"}}, "required": []}}},
]

VISIBLE_BUG_TESTS = '''from inventory import Item, Warehouse, price_with_tax, bulk_discount
import pytest


def test_tax():
    assert price_with_tax(100) == 120.0
    assert price_with_tax(50, "DE") == 59.5


def test_discount_boundaries():
    assert bulk_discount(9) == 0.0
    assert bulk_discount(10) == 0.05
    assert bulk_discount(50) == 0.10
    assert bulk_discount(100) == 0.15


def test_remove_too_many():
    w = Warehouse("w")
    w.add(Item("X", "x", 1.0, 3))
    with pytest.raises(ValueError):
        w.remove("X", 5)
    assert w.items["X"].qty == 3
'''

TASKS = {
 "t1_bugfix_tax": dict(
   prompt="Users report that price_with_tax returns wrong values: price_with_tax(100) returns 20.0 but it should return the gross price 120.0 (net amount plus VAT). Fix the bug.",
   hidden='''from inventory import price_with_tax
def test_h():
    assert price_with_tax(100) == 120.0
    assert price_with_tax(100, "CH") == 108.1
    assert price_with_tax(19.99, "DE") == 23.79
'''),
 "t2_bugfix_discount": dict(
   prompt="bulk_discount() does not behave the way its docstring documents. Make the implementation match the documented behavior.",
   hidden='''from inventory import bulk_discount
def test_h():
    assert [bulk_discount(q) for q in (0, 9, 10, 11, 49, 50, 99, 100, 500)] == [0.0, 0.0, 0.05, 0.05, 0.05, 0.10, 0.10, 0.15, 0.15]
'''),
 "t3_feature_remove": dict(
   prompt="Make Warehouse.remove safer: removing more units than are in stock must raise ValueError and leave the stock unchanged; removing a non-positive quantity must raise ValueError; removing an unknown SKU must raise KeyError. Removing exactly all units should still delete the item. Add a new test file tests/test_remove.py covering these cases and make sure the whole suite passes.",
   hidden='''import pytest, os
from inventory import Item, Warehouse
def mk():
    w = Warehouse("w"); w.add(Item("A", "a", 2.0, 5)); return w
def test_h():
    w = mk()
    with pytest.raises(ValueError): w.remove("A", 6)
    assert w.items["A"].qty == 5
    with pytest.raises(ValueError): w.remove("A", 0)
    with pytest.raises(ValueError): w.remove("A", -1)
    with pytest.raises(KeyError): w.remove("ZZ", 1)
    w.remove("A", 2); assert w.items["A"].qty == 3
    w.remove("A", 3); assert "A" not in w.items
def test_has_tests():
    assert os.path.exists("tests/test_remove.py")
'''),
 "t4_feature_lowstock": dict(
   prompt="Add low-stock reporting: (1) add a function low_stock(wh) to inventory/report.py that returns a sorted list of SKUs whose qty is strictly below the LOW_STOCK_THRESHOLD defined in the config module (read the current value at call time, since it can be changed at runtime); (2) in stock_report, append ' (LOW)' to the end of the line of every such item; (3) export low_stock from the inventory package so `from inventory import low_stock` works. Add tests for it.",
   hidden='''from inventory import Item, Warehouse, low_stock
from inventory.report import stock_report
from inventory import config
def test_h(monkeypatch):
    w = Warehouse("w")
    w.add(Item("B2", "nut", 0.1, 4)); w.add(Item("A1", "bolt", 0.5, 5)); w.add(Item("C3", "gear", 9.0, 0)); w.add(Item("D4", "pin", 0.2, 100))
    assert low_stock(w) == ["B2", "C3"]
    rep = stock_report(w).splitlines()
    assert rep[0] == "Warehouse: w"
    low = [l for l in rep[1:] if l.endswith(" (LOW)")]
    assert len(low) == 2 and low[0].startswith("B2") and low[1].startswith("C3")
    assert not any(l.endswith("(LOW)") for l in rep[1:] if l.startswith(("A1", "D4")))
    monkeypatch.setattr(config, "LOW_STOCK_THRESHOLD", 1)
    assert low_stock(w) == ["C3"]
'''),
 "t5_explore_question": dict(
   prompt="Do not modify any files. Answer this question about the codebase: what VAT rate (as the fraction stored in the code) is used for Switzerland, and what is the default region code? End your final message with a line of the form: ANSWER: <rate>, <region>",
   answer_re=r"ANSWER:\s*\**\s*0?\.081\s*,\s*AT\b", readonly=True),
 "t6_feature_csv": dict(
   prompt="Add CSV persistence to Warehouse: an instance method to_csv(path) that writes the items (header row: sku,name,unit_price,qty; one row per item sorted by sku) and a classmethod from_csv(path, name) that reconstructs a Warehouse. Use the csv module so names containing commas or quotes round-trip correctly. Numeric fields must come back as float/int. Add tests.",
   hidden='''from inventory import Item, Warehouse
def test_h(tmp_path):
    w = Warehouse("w")
    w.add(Item("Z9", 'Bolt, "hex" 5mm', 0.25, 40)); w.add(Item("A1", "nut", 1.5, 2))
    p = tmp_path / "x.csv"; w.to_csv(str(p))
    lines = p.read_text().splitlines()
    assert lines[0].strip() == "sku,name,unit_price,qty"
    assert lines[1].startswith("A1")
    w2 = Warehouse.from_csv(str(p), "copy")
    assert w2.name == "copy"
    assert w2.items["Z9"].name == 'Bolt, "hex" 5mm'
    assert w2.items["Z9"].qty == 40 and isinstance(w2.items["Z9"].qty, int)
    assert w2.items["A1"].unit_price == 1.5
    assert w2.total_value() == w.total_value()
'''),
 "t7_refactor_rename": dict(
   prompt="Refactor: rename the Item field `unit_price` to `price` everywhere in the repository (library code and tests), keeping all behavior the same. Make sure the tests pass afterwards.",
   hidden='''import subprocess
from inventory import Item, Warehouse
def test_h():
    it = Item("A", "a", price=2.0, qty=3)
    w = Warehouse("w"); w.add(it)
    assert w.total_value() == 6.0
    out = subprocess.run(["grep", "-rn", "unit_price", "inventory", "tests"], capture_output=True, text=True).stdout
    assert "unit_price" not in "\\n".join(l for l in out.splitlines() if "test_hidden" not in l)
'''),
 "t8_multi_bug": dict(
   prompt="The test suite is failing. Run the tests, find the bugs in the library code and fix all of them. Do not modify any test files.",
   setup={"tests/test_more.py": VISIBLE_BUG_TESTS},
   protect=["tests/test_more.py", "tests/test_basic.py"],
   hidden='''from inventory import Item, Warehouse, price_with_tax, bulk_discount
import pytest
def test_h():
    assert price_with_tax(10, "FR") == 12.0
    assert bulk_discount(10) == 0.05 and bulk_discount(100) == 0.15 and bulk_discount(9) == 0
    w = Warehouse("w"); w.add(Item("X", "x", 1.0, 3))
    with pytest.raises(ValueError): w.remove("X", 4)
    w.remove("X", 3); assert "X" not in w.items
'''),
 "t9_cli": dict(
   prompt="Add a command-line interface module inventory/cli.py with a function main(argv=None) -> int using argparse. It operates on a CSV stock file given by a required global option --db PATH (columns sku,name,unit_price,qty; create the file with just the header if it does not exist). Subcommands: `add SKU NAME PRICE QTY` (adds stock, merging with an existing SKU), `remove SKU QTY` (exit code 2 and an error message on stderr if the SKU is unknown or there is not enough stock; the file must stay unchanged in that case), and `report` (prints the stock_report of the warehouse to stdout; the warehouse name is the file's base name without extension). Return 0 on success. Also make `python -m inventory.cli` work. Add tests.",
   hidden="""import os, subprocess, sys
from inventory.cli import main
def test_h(tmp_path, capsys):
    db = str(tmp_path / "shop.csv")
    assert main(["--db", db, "add", "A1", "bolt", "0.5", "10"]) == 0
    assert main(["--db", db, "add", "A1", "bolt", "0.5", "5"]) == 0
    assert main(["--db", db, "add", "B2", "big nut", "1.25", "3"]) == 0
    before = open(db).read()
    assert main(["--db", db, "remove", "A1", "99"]) == 2
    assert main(["--db", db, "remove", "ZZ", "1"]) == 2
    assert open(db).read() == before
    assert main(["--db", db, "remove", "A1", "4"]) == 0
    capsys.readouterr()
    assert main(["--db", db, "report"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "Warehouse: shop"
    assert any(l.startswith("A1") and l.split()[-1] == "11" for l in out)
    assert any(l.startswith("B2") and "big nut" in l for l in out)
    r = subprocess.run([sys.executable, "-m", "inventory.cli", "--db", db, "report"], capture_output=True, text=True)
    assert r.returncode == 0 and "Warehouse: shop" in r.stdout
"""),
 "t10_threadsafe": dict(
   prompt="Warehouse is used from multiple threads in production and stock counts get corrupted. Make Warehouse.add, Warehouse.remove and Warehouse.total_value thread-safe (a per-instance lock is fine; keep the dataclass interface and existing behavior, and the class must remain copyable with copy.deepcopy). Add a test that hammers it from several threads.",
   hidden="""import threading, copy, sys
from inventory import Item, Warehouse
def test_h():
    sys.setswitchinterval(1e-6)
    for rnd in range(8):
        w = Warehouse("w")
        def worker():
            for _ in range(4000):
                w.add(Item("A", "a", 1.0, 1))
                w.add(Item("T", "t", 1.0, 2)); w.remove("T", 1); w.remove("T", 1)
        ts = [threading.Thread(target=worker) for _ in range(8)]
        [t.start() for t in ts]; [t.join() for t in ts]
        assert w.items["A"].qty == 32000
        assert "T" not in w.items
    w2 = copy.deepcopy(w)
    w2.add(Item("B", "b", 2.0, 1))
    assert "B" not in w.items and w2.total_value() == 32002.0
"""),
 "t11_money": dict(
   prompt="Accounting complains that Warehouse.total_value() and price_with_tax() produce floating point artefacts (e.g. 0.1*3 style errors). Change the money math to use decimal.Decimal internally so that results are exact to the cent: total_value() must return a Decimal rounded to 2 decimal places (ROUND_HALF_UP), and price_with_tax() must return a Decimal rounded the same way. unit_price may still be passed in as float or str or Decimal; floats must be converted via str() to avoid binary artefacts. Keep the existing tests working (update their expectations to Decimal where needed).",
   setup={"inventory/pricing.py": open(os.path.join(FIX, "inventory", "pricing.py")).read().replace("amount * rate", "amount * (1 + rate)")},
   hidden="""from decimal import Decimal
from inventory import Item, Warehouse, price_with_tax
def test_h():
    w = Warehouse("w")
    w.add(Item("A", "a", 0.1, 3)); w.add(Item("B", "b", "0.105", 1)); w.add(Item("C", "c", Decimal("19.99"), 2))
    v = w.total_value()
    assert isinstance(v, Decimal) and v == Decimal("40.39")
    assert price_with_tax(Decimal("0.125"), "AT") == Decimal("0.15")
    assert price_with_tax(19.99, "DE") == Decimal("23.79")
    assert isinstance(price_with_tax(1, "CH"), Decimal)
"""),
 "t12_misleading": dict(
   prompt="A customer reports: 'After removing items, stock_report sometimes still shows SKUs with 0 units, and total_value is wrong after merging items with different prices.' Investigate the code, find the root causes, and fix them. Policy: when the same SKU is added again with a different unit_price, the stored unit_price becomes the quantity-weighted average price (rounded to 4 decimals); an item must disappear from the warehouse as soon as its qty reaches 0 by any path (including add with qty 0 of a new SKU, which should not create an entry). Add regression tests.",
   hidden="""from inventory import Item, Warehouse
from inventory.report import stock_report
def test_h():
    w = Warehouse("w")
    w.add(Item("A", "a", 1.0, 2)); w.add(Item("A", "a", 4.0, 1))
    assert w.items["A"].unit_price == 2.0 and w.items["A"].qty == 3
    assert w.total_value() == 6.0
    w.add(Item("N", "n", 1.0, 0))
    assert "N" not in w.items
    w.remove("A", 3)
    assert "A" not in w.items and stock_report(w) == "Warehouse: w"
    w.add(Item("B", "b", 1.0, 3)); w.add(Item("B", "b", 2.0, 0))
    assert w.items["B"].unit_price == 1.0
"""),
}


def snapshot(d):
    h = {}
    for root, _, files in os.walk(d):
        if "__pycache__" in root or ".pytest_cache" in root: continue
        for f in files:
            p = os.path.join(root, f)
            h[os.path.relpath(p, d)] = hashlib.md5(open(p, "rb").read()).hexdigest()
    return h


class Env:
    def __init__(self, wd): self.wd = wd
    def safe(self, p):
        full = os.path.normpath(os.path.join(self.wd, p))
        if not full.startswith(self.wd): raise ValueError("path outside repository")
        return full
    def list_files(self):
        return "\n".join(sorted(k for k in snapshot(self.wd)))
    def read_file(self, path):
        txt = open(self.safe(path)).read()
        return "\n".join(f"{i+1:4d}| {l}" for i, l in enumerate(txt.splitlines()))
    def write_file(self, path, content):
        p = self.safe(path); os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").write(content); return f"wrote {len(content)} chars to {path}"
    def edit_file(self, path, old, new):
        p = self.safe(path); txt = open(p).read(); n = txt.count(old)
        if n != 1: return f"ERROR: 'old' text occurs {n} times in {path} (must be exactly once)"
        open(p, "w").write(txt.replace(old, new)); return f"edited {path}"
    def grep(self, pattern):
        out = []
        rx = re.compile(pattern)
        for f in sorted(snapshot(self.wd)):
            try:
                for i, l in enumerate(open(os.path.join(self.wd, f)).read().splitlines()):
                    if rx.search(l): out.append(f"{f}:{i+1}:{l}")
            except UnicodeDecodeError: pass
        return "\n".join(out[:100]) or "(no matches)"
    def run_tests(self, path=None):
        cmd = [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider"] + ([path] if path else [])
        p = subprocess.run(cmd, cwd=self.wd, capture_output=True, text=True, timeout=120)
        return (p.stdout + p.stderr)[-6000:]


def run_task(url, name, spec, max_turns=30, max_tokens=8192):
    wd = tempfile.mkdtemp(prefix=f"agent_{name}_")
    shutil.copytree(FIX, wd, dirs_exist_ok=True)
    for p, c in spec.get("setup", {}).items(): open(os.path.join(wd, p), "w").write(c)
    before = snapshot(wd); env = Env(wd)
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": spec["prompt"]}]
    st = dict(turns=0, calls=0, bad_calls=0, tool_errors=0, prompt_tok=0, compl_tok=0, prefill_s=0.0, gen_s=0.0, http_err=0, length_stops=0)
    t0 = time.time(); final = ""
    for turn in range(max_turns):
        body = dict(messages=msgs, tools=TOOLS, max_tokens=max_tokens, temperature=1.0, top_p=0.95, top_k=20, min_p=0.0,
                    chat_template_kwargs={"enable_thinking": True, "preserve_thinking": False, "reasoning_effort": "medium"})
        try:
            r = requests.post(url + "/v1/chat/completions", json=body, timeout=1800)
            if r.status_code != 200:
                st["http_err"] += 1; final = f"HTTP {r.status_code} {r.text[:200]}"; break
            j = r.json()
        except Exception as e:
            st["http_err"] += 1; final = f"EXC {e}"; break
        st["turns"] += 1
        u = j.get("usage", {}); tm = j.get("timings", {})
        st["prompt_tok"] += u.get("prompt_tokens", 0); st["compl_tok"] += u.get("completion_tokens", 0)
        st["prefill_s"] += tm.get("prompt_ms", 0) / 1000; st["gen_s"] += tm.get("predicted_ms", 0) / 1000
        ch = j["choices"][0]; m = ch["message"]
        if ch.get("finish_reason") == "length": st["length_stops"] += 1
        calls = m.get("tool_calls") or []
        msgs.append({"role": "assistant", "content": m.get("content") or "", **({"tool_calls": calls} if calls else {})})
        if not calls:
            final = m.get("content") or ""
            if ch.get("finish_reason") == "length":
                msgs.append({"role": "user", "content": "Your reply was cut off. Continue."}); continue
            break
        for c in calls:
            st["calls"] += 1
            fn = c.get("function", {}).get("name"); raw = c.get("function", {}).get("arguments", "{}")
            try:
                args = json.loads(raw) if isinstance(raw, str) else raw
                if fn not in {t["function"]["name"] for t in TOOLS}: raise KeyError(f"unknown tool {fn}")
                res = getattr(env, fn)(**args)
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                st["bad_calls"] += 1; res = f"ERROR: invalid tool call: {type(e).__name__}: {e}"
            except Exception as e:
                st["tool_errors"] += 1; res = f"ERROR: {type(e).__name__}: {e}"
            if len(res) > 8000: res = res[:8000] + "\n...[truncated]"
            msgs.append({"role": "tool", "tool_call_id": c.get("id", ""), "content": res})
    st["wall_s"] = round(time.time() - t0, 1)
    # ---- grading
    after = snapshot(wd); why = []
    if spec.get("readonly"):
        ok = bool(re.search(spec["answer_re"], final, re.I)) and before == after
        if before != after: why.append("modified files")
        if not re.search(spec["answer_re"], final, re.I): why.append(f"answer: {final[-120:]!r}")
    else:
        for p in spec.get("protect", []):
            if before.get(p) != after.get(p): why.append(f"modified protected {p}")
        open(os.path.join(wd, "tests", "test_hidden.py"), "w").write(spec["hidden"])
        p = subprocess.run([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=wd, capture_output=True, text=True, timeout=180)
        if p.returncode != 0: why.append("tests: " + (p.stdout.strip().splitlines() or ["?"])[-1][:150])
        ok = not why
    st.update(ok=ok, why="; ".join(why) or "ok", final=final[-300:])
    json.dump(msgs, open(os.path.join(wd, "transcript.json"), "w"), indent=1)
    st["workdir"] = wd
    return st


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=os.environ.get("BENCH_URL", "http://127.0.0.1:8091")); ap.add_argument("--tag", required=True)
    ap.add_argument("--only", default=""); ap.add_argument("--repeat", type=int, default=1)
    a = ap.parse_args()
    out = os.path.join(RES, a.tag); os.makedirs(out, exist_ok=True)
    write_params(out, a.url, dict(suite="agent", sampling=dict(temperature=1.0, top_p=0.95, top_k=20, min_p=0.0),
                 chat_template_kwargs={"enable_thinking": True, "preserve_thinking": False, "reasoning_effort": "medium"},
                 max_tokens_per_turn=8192, max_turns=30, repeat=a.repeat, only=a.only))
    fn = os.path.join(out, "agent.jsonl")
    names = [n for n in TASKS if not a.only or n in a.only.split(",")]
    for rep in range(a.repeat):
        for n in names:
            st = run_task(a.url, n, TASKS[n]); st.update(task=n, rep=rep)
            open(fn, "a").write(json.dumps(st) + "\n")
            print(f"{n:22s} {'PASS' if st['ok'] else 'FAIL'} turns={st['turns']:2d} calls={st['calls']:2d} bad={st['bad_calls']} "
                  f"tok={st['compl_tok']:6d} ptok={st['prompt_tok']:7d} wall={st['wall_s']:6.1f}s  {st['why'][:90]}", flush=True)
    recs = [json.loads(l) for l in open(fn)]
    s = dict(tag=a.tag, n=len(recs), pass_rate=round(sum(r["ok"] for r in recs) / len(recs), 3),
             bad_calls=sum(r["bad_calls"] for r in recs), calls=sum(r["calls"] for r in recs),
             http_err=sum(r["http_err"] for r in recs), length_stops=sum(r["length_stops"] for r in recs),
             avg_wall_s=round(sum(r["wall_s"] for r in recs) / len(recs), 1),
             avg_turns=round(sum(r["turns"] for r in recs) / len(recs), 1))
    json.dump(s, open(os.path.join(out, "agent_summary.json"), "w"), indent=1); print(json.dumps(s))


if __name__ == "__main__":
    main()
