"""Pick one real fixed-low run and write it as a trace for the dashboard."""
import json, sys
from pathlib import Path
import grade
from agent.tools import CaseTools

HARD = ["bad_join_key", "duplicate_keys", "null_explosion", "unit_change"]  # preference order
labels = grade.load_labels("cases/labels.jsonl")
runs = {}
for l in open("runs/fixed_low_v2.jsonl"):
    r = json.loads(l)
    runs[r["case_id"]] = r

ok = []
for cid, r in runs.items():
    lab = labels[cid]
    if (lab["failure_type"] in HARD and 6 <= r["n_steps"] <= 9 and r["status"] == "submitted"
            and grade.grade_case(r, lab)["success"]):
        ok.append(r)
        print(cid, lab["failure_type"], r["n_steps"], "steps", r["wall_s"], "s")

pick = sys.argv[1] if len(sys.argv) > 1 else sorted(
    ok, key=lambda r: (HARD.index(labels[r["case_id"]]["failure_type"]), r["n_steps"]))[0]["case_id"]
rec, lab = runs[pick], labels[pick]
case_dir = Path("cases") / pick
tools = CaseTools(case_dir)

steps = []
for s in rec["steps"]:
    calls = []
    for t in s["tools"]:
        if t["name"] == "submit_diagnosis":
            continue
        try:
            args = json.loads(t["args"] or "{}")
        except Exception:
            args = {"raw": t["args"]}
        out = tools.call(t["name"], t["args"])
        calls.append({"name": t["name"], "args": args, "out": out[:400] + ("..." if len(out) > 400 else "")})
    steps.append({"step": s["step"], "latency_s": s["latency_s"], "reasoning_tokens": s["reasoning_tokens"], "calls": calls})

g = grade.grade_case(rec, lab)
trace = {
    "case_id": pick, "failure_type": lab["failure_type"], "alert": (case_dir / "alert.txt").read_text(),
    "label": {"file": lab.get("file"), "column": lab.get("column")},
    "prediction": rec["prediction"], "graded": g,
    "n_steps": rec["n_steps"], "wall_s": rec["wall_s"], "out_tokens": rec["total_completion_tokens"],
    "steps": steps,
}
Path("web/public/data/trace.json").write_text(json.dumps(trace, indent=1))
print("\nPICKED", pick, lab["failure_type"], g)
print("ALERT:", trace["alert"][:300])
for s in steps:
    for c in s["calls"]:
        print(f"step {s['step']} {c['name']}({json.dumps(c['args'])[:100]}) -> {c['out'][:120]!r}")
print("PRED:", rec["prediction"])
