"""Summarize the Muse Spark 1.3 baseline in the same per-success terms as cost_model.py."""
import json
import grade

P = {"in": 1.25, "cached": 0.15, "out": 4.25}   # Spark 1.3 standard, per 1M, checked Nov 3 2026
labels = grade.load_labels("cases/labels.jsonl")
runs = {}
for l in open("runs/spark.jsonl"):
    r = json.loads(l)
    runs[r["case_id"]] = r

n = len(runs)
succ = sum(grade.grade_case(r, labels[c])["success"] for c, r in runs.items())
tot = lambda k: sum(r[k] or 0 for r in runs.values())
inp, cached, out, wall = tot("total_prompt_tokens"), tot("total_cached_tokens"), tot("total_completion_tokens"), tot("wall_s")
spent = ((inp - cached) * P["in"] + cached * P["cached"] + out * P["out"]) / 1e6

cm = json.load(open("runs/cost_model.json"))
low = cm["levels"]["low"]
s = {
    "model": "muse-spark-1.3", "prices": P, "n": n, "success": succ,
    "steps": round(sum(r["n_steps"] for r in runs.values()) / n, 1),
    "in_tok_per_success": round(inp / succ), "cached_tok_per_success": round(cached / succ),
    "out_tok_per_success": round(out / succ), "cache_share": round(cached / inp, 3),
    "s_per_success": round(wall / succ, 1), "cost_per_task": round(spent / succ, 5),
    "total_spent_usd": round(spent, 3),
    "statuses": {st: sum(r["status"] == st for r in runs.values()) for st in {r["status"] for r in runs.values()}},
    "vs_glimmer_low": {
        "deepinfra_cost_per_task": low["api_cost_per_task"]["deepinfra"],
        "l4_spot_full_cost_per_task": round(cm["gpu_hourly"]["spot"] * 24 / low["cap_per_day"], 5),
    },
}
json.dump(s, open("runs/spark_summary.json", "w"), indent=1)
print(json.dumps(s, indent=1))
