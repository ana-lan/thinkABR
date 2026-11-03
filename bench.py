"""Phase 3.3: throughput/latency at several agent concurrency levels on one L4.
  python bench.py --level low --conc 1,4,8 --tag prefix_on
"""
import argparse, json, re, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import grade
from agent.loop import fixed_policy, run_case

NAMES = ["vllm:kv_cache_usage_perc", "vllm:num_requests_waiting", "vllm:num_requests_running",
         "vllm:num_preemptions_total", "vllm:prefix_cache_hits_total",
         "vllm:prefix_cache_queries_total", "vllm:generation_tokens_total"]

def metrics(base):
    txt = urllib.request.urlopen(base + "/metrics", timeout=5).read().decode()
    out = {}
    for n in NAMES:
        v = [float(m.group(1)) for m in re.finditer(
            r"^" + re.escape(n) + r"(?:\{[^}]*\})?\s+([0-9.eE+-]+)$", txt, re.M)]
        out[n] = sum(v) if v else 0.0
    return out

class Poller(threading.Thread):
    def __init__(self, base):
        super().__init__(daemon=True); self.base, self.stop, self.samples = base, False, []
    def run(self):
        while not self.stop:
            try: self.samples.append(metrics(self.base))
            except Exception: pass
            time.sleep(1)

def d(m0, m1, k): return m1[k] - m0[k]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", default="low")
    ap.add_argument("--conc", default="1,4,8")
    ap.add_argument("--tag", default="prefix_on")
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--per_type", type=int, default=1)
    a = ap.parse_args()
    labels = grade.load_labels("cases/labels.jsonl")
    seen, ids = set(), []
    for cid in sorted(labels):
        t = labels[cid]["failure_type"]
        if sum(labels[i]["failure_type"] == t for i in ids) < a.per_type: ids.append(cid)
    print("cases:", ids, flush=True)
    for c in map(int, a.conc.split(",")):
        print(f"conc={c} starting {time.strftime('%H:%M')}", flush=True)
        m0, p = metrics(a.base), Poller(a.base); p.start()
        t0 = time.time()
        with ThreadPoolExecutor(c) as ex:
            recs = list(ex.map(lambda cid: run_case(Path("cases") / cid, fixed_policy(a.level), base=a.base), ids))
        wall = time.time() - t0
        p.stop = True; p.join(); m1 = metrics(a.base)
        ok = sum(grade.grade_case(r, labels[r["case_id"]])["success"] for r in recs)
        lat = sorted(r["wall_s"] for r in recs)
        q = d(m0, m1, "vllm:prefix_cache_queries_total")
        s = p.samples or [m1]
        row = {"tag": a.tag, "level": a.level, "conc": c, "n": len(recs), "success": ok,
               "wall_s": round(wall, 1), "tasks_per_hr": round(len(recs) / wall * 3600, 1),
               "case_lat_mean": round(sum(lat) / len(lat), 1), "case_lat_max": round(lat[-1], 1),
               "gen_tok_per_s": round(d(m0, m1, "vllm:generation_tokens_total") / wall, 1),
               "prefix_hit": round(d(m0, m1, "vllm:prefix_cache_hits_total") / q, 3) if q else None,
               "preemptions": int(d(m0, m1, "vllm:num_preemptions_total")),
               "kv_peak": round(max(x["vllm:kv_cache_usage_perc"] for x in s), 3),
               "waiting_peak": int(max(x["vllm:num_requests_waiting"] for x in s)),
               "statuses": sorted(r["status"] for r in recs)}
        print(json.dumps(row), flush=True)
        with open("runs/bench.jsonl", "a") as f: f.write(json.dumps(row) + "\n")

if __name__ == "__main__":
    main()
