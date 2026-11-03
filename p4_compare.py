import json, sys, collections, grade
L = grade.load_labels(sys.argv[1])
def summ(path):
    rows = [json.loads(l) for l in open(path)]
    ok = [r for r in rows if grade.grade_case(r, L[r["case_id"]])["success"]]
    n, k = len(rows), max(len(ok), 1)
    esc = [e for r in rows for e in r.get("router_events", [])]
    return {
        "n": n, "success": len(ok),
        "steps": round(sum(r["n_steps"] for r in rows) / n, 1),
        "reasoning_tok": round(sum(r["total_reasoning_tokens"] or 0 for r in rows) / n),
        "out_tok_per_success": round(sum(r["total_completion_tokens"] for r in rows) / k),
        "s_per_success": round(sum(r["wall_s"] for r in rows) / k),
        "cache_hit": round(sum(r["prefix_cache_hit_rate"] or 0 for r in rows) / n, 3),
        "status": dict(collections.Counter(r["status"] for r in rows)),
        "escalated_cases": sum(1 for r in rows if r.get("router_events")),
        "escalations": [e["reason"] for e in esc],
    }
out = {"router": summ("runs/router.jsonl"),
       "fixed_low": summ("runs/fixed_low_v2.jsonl"),
       "fixed_high": summ("runs/fixed_high_v2.jsonl")}
json.dump(out, open("runs/router_summary.json", "w"), indent=1)
for k, v in out.items(): print(k, v)
