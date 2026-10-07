#!/usr/bin/env python3
"""external_params.py <url> <compose-dir> [run-tag ...]

Describe a server that is NOT launched by serve.sh (e.g. halogen-flash-server under docker compose), read-only:
the compose file's engine environment, the running containers' image/env (via `sudo docker inspect`, if allowed),
and the server's /health. Writes results/$BENCH_HW/logs/current_server.json (picked up by later bench runs) and
patches the "server" field of params.json in each given run tag.
"""
import json, os, subprocess, sys, time
import requests

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
url, cdir, tags = sys.argv[1], os.path.expanduser(sys.argv[2]), sys.argv[3:]
hw = os.environ.get("BENCH_HW", "unknown-hw")

def sh(cmd):
    try: return subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL, timeout=30).decode()
    except Exception: return ""

containers = []
for cid in sh("sudo -n docker ps -q").split():
    try:
        c = json.loads(sh(f"sudo -n docker inspect {cid}"))[0]
        containers.append({"name": c["Name"].lstrip("/"), "image": c["Config"]["Image"], "cmd": c["Config"]["Cmd"],
                           "env": sorted(e for e in c["Config"]["Env"] if e.startswith("HALOGEN_")),
                           "mounts": [f'{m["Source"]}:{m["Destination"]}:{"rw" if m["RW"] else "ro"}' for m in c["Mounts"]]})
    except Exception: pass
try: health = requests.get(url + "/health", timeout=10).json()
except Exception as e: health = f"unavailable: {e}"
srv = {"config": "external", "mode": "external", "url": url, "compose_dir": cdir,
       "cmd": "sudo docker compose up -d   (in %s)" % cdir,
       "compose_file": open(os.path.join(cdir, "docker-compose.yml")).read(),
       "compose_git": sh(f"git -C {cdir} log -1 --format='%h %cd %s'").strip() + " + local changes: " +
                      sh(f"git -C {cdir} status --porcelain").strip().replace("\n", ", "),
       "containers": containers, "health": health, "recorded": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
logdir = os.path.join(REPO, "results", hw, "logs"); os.makedirs(logdir, exist_ok=True)
json.dump(srv, open(os.path.join(logdir, "current_server.json"), "w"), indent=1)
for t in tags:
    fn = os.path.join(REPO, "results", hw, "runs", t, "params.json")
    p = json.load(open(fn)); p["server"] = srv; json.dump(p, open(fn, "w"), indent=1); print("patched", fn)
print("containers:", [c["name"] + " " + c["image"] for c in containers])
