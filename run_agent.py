"""Run the triage agent over cases at a fixed reasoning level. Resumable.

  python run_agent.py --level high --cases case_000,case_011 -v
  python run_agent.py --level low --all                  # writes runs/fixed_low.jsonl
  python run_agent.py --level high --all --strip         # ablation: past reasoning removed

One JSON line per finished case. Rerunning skips cases already in the output file,
so a spot preemption only loses the case that was in flight.
"""
import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent.loop import fixed_policy, run_case

LEVELS = ["low", "medium", "high", "xhigh"]


def wait_for_server(base, timeout=900):
    """Block until vLLM answers /v1/models (it takes ~3 min after a VM start)."""
    t0 = time.time()
    while True:
        try:
            urllib.request.urlopen(f"{base}/v1/models", timeout=5)
            return
        except Exception:
            if time.time() - t0 > timeout:
                sys.exit(f"server at {base} not up after {timeout}s")
            print("waiting for vLLM ...", flush=True)
            time.sleep(15)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", choices=LEVELS, default="high")
    ap.add_argument("--cases-dir", default="cases")
    ap.add_argument("--cases", help="comma-separated case ids")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--strip", action="store_true", help="drop past reasoning from history")
    ap.add_argument("--out", help="default runs/fixed_<level>[_strip].jsonl")
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()

    cdir = Path(a.cases_dir)
    if a.all:
        ids = sorted(p.name for p in cdir.glob("case_*") if p.is_dir())
    elif a.cases:
        ids = [c.strip() for c in a.cases.split(",")]
    else:
        sys.exit("pass --cases or --all")

    out = Path(a.out or f"runs/fixed_{a.level}{'_strip' if a.strip else ''}.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        done = {json.loads(l)["case_id"] for l in out.open() if l.strip()}
    todo = [c for c in ids if c not in done]
    print(f"{out}: {len(done)} done, {len(todo)} to run")
    if todo:
        wait_for_server(a.base)

    for i, cid in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {cid} level={a.level}")
        res = run_case(cdir / cid, fixed_policy(a.level), keep_reasoning=not a.strip,
                       base=a.base, verbose=a.verbose)
        res.update({"run": out.stem, "policy": f"fixed_{a.level}", "ts": time.strftime("%Y-%m-%dT%H:%M:%S")})
        with out.open("a") as f:
            f.write(json.dumps(res) + "\n")
        p = res["prediction"] or {}
        print(f"   {res['status']}  steps={res['n_steps']}  {res['wall_s']}s  "
              f"reason_tok={res['total_reasoning_tokens']}  cache={res['prefix_cache_hit_rate']}  "
              f"-> {p.get('failure_type')} {p.get('file')}:{p.get('column')}")


if __name__ == "__main__":
    main()
