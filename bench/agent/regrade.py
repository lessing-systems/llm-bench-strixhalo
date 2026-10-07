"""Re-run current hidden tests against saved agent workdirs (fixes grading bugs post-hoc)."""
import json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agent_bench as A
for tag in sys.argv[1:]:
    fn = os.path.join(A.RES, tag, "agent.jsonl")
    recs = [json.loads(l) for l in open(fn)]
    changed = 0
    for r in recs:
        spec = A.TASKS[r["task"]]
        if spec.get("readonly") or not os.path.isdir(r["workdir"]): continue
        wd = r["workdir"]
        open(os.path.join(wd, "tests", "test_hidden.py"), "w").write(spec["hidden"])
        p = subprocess.run([A.PY, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=wd, capture_output=True, text=True, timeout=300)
        prot = [x for x in r["why"].split("; ") if x.startswith("modified protected")]
        ok = p.returncode == 0 and not prot
        if ok != r["ok"]:
            changed += 1; print(f"{tag} rep{r['rep']} {r['task']}: {r['ok']} -> {ok}")
        r["ok"] = ok; r["why"] = "; ".join(prot + ([] if p.returncode == 0 else ["tests: " + p.stdout.strip().splitlines()[-1][:150]])) or "ok"
    with open(fn, "w") as f:
        for r in recs: f.write(json.dumps(r) + "\n")
    print(tag, f"pass={sum(r['ok'] for r in recs)}/{len(recs)} changed={changed}")
