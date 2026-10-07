"""Write params.json into a run directory: server command/env (from serve.sh), request settings, versions."""
import json, os, subprocess, time
import requests

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def write_params(outdir, url, request_settings, extra=None):
    hw = os.environ.get("BENCH_HW", "unknown-hw")
    logdir = os.environ.get("BENCH_LOGDIR") or os.path.join(REPO, "results", hw, "logs")
    p = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "bench_hw": hw, "url": url,
         "request": request_settings, "reconstructed": False}
    try: p["server"] = json.load(open(os.path.join(logdir, "current_server.json")))
    except Exception: p["server"] = None
    try:
        props = requests.get(url + "/props", timeout=10).json()
        p["server_props"] = {k: props.get(k) for k in ("model_path", "n_ctx", "total_slots", "build_info", "chat_template_caps") if k in props}
        dgs = props.get("default_generation_settings") or {}
        p["server_props"]["n_ctx_slot"] = dgs.get("n_ctx")
    except Exception as e:
        p["server_props"] = f"unavailable: {e}"
    try: p["bench_commit"] = subprocess.check_output(["git", "-C", REPO, "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
    except Exception: p["bench_commit"] = None
    if extra: p.update(extra)
    os.makedirs(outdir, exist_ok=True)
    fn = os.path.join(outdir, "params.json")
    # keep a history if a run directory is reused (e.g. --repeat continuation)
    hist = []
    if os.path.exists(fn):
        old = json.load(open(fn)); hist = old.pop("history", []) + [old]
    if hist: p["history"] = hist
    json.dump(p, open(fn, "w"), indent=1)
