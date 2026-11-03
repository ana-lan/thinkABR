"""Phase 2.6: grade agent runs against ground truth.

  python grade.py runs/fixed_high.jsonl                 # one run, full breakdown
  python grade.py runs/fixed_*.jsonl                    # side-by-side comparison
  python grade.py runs/fixed_high.jsonl --cases-only    # per-case table

A case is a success when failure_type, file and column all match the label.
- column is ignored for missing_file (the whole file is the problem)
- for renamed_column, either the original or the new upstream name counts
- column matching ignores case and a table prefix (orders.amount == amount)
The free-text fix is not graded here (optional Spark grading later).
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


def load_labels(path):
    labels = {}
    for l in map(json.loads, open(path)):
        alts = {l["column"]} if l["column"] else set()
        if l["failure_type"] == "renamed_column":
            m = re.search(r"renamed (\w+) to (\w+)", l["fix"])
            if m:
                alts.add(m.group(2))
        l["accepted_columns"] = {a.lower() for a in alts}
        labels[l["case_id"]] = l
    return labels


def norm_col(c):
    if not c:
        return None
    return str(c).strip().strip('"`').split(".")[-1].lower()


def grade_case(rec, label):
    p = rec.get("prediction") or {}
    type_ok = p.get("failure_type") == label["failure_type"]
    file_ok = (p.get("file") or "").lower() == label["file"].lower()
    if label["failure_type"] == "missing_file":
        col_ok = True
    else:
        col_ok = norm_col(p.get("column")) in label["accepted_columns"]
    return {"type_ok": type_ok, "file_ok": file_ok, "col_ok": col_ok,
            "success": bool(p) and type_ok and file_ok and col_ok}


def load_run(path, labels):
    rows = []
    for rec in map(json.loads, open(path)):
        lab = labels.get(rec["case_id"])
        if lab is None:
            continue
        g = grade_case(rec, lab)
        rows.append({**rec, **g, "truth": lab})
    return rows


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else float("nan")


def summarize(rows):
    n = len(rows)
    ok = [r for r in rows if r["success"]]
    s = {
        "cases": n,
        "success": len(ok),
        "success_rate": len(ok) / n if n else float("nan"),
        "type_acc": _mean([r["type_ok"] for r in rows]),
        "file_acc": _mean([r["file_ok"] for r in rows]),
        "col_acc": _mean([r["col_ok"] for r in rows]),
        "steps": _mean([r["n_steps"] for r in rows]),
        "wall_s": _mean([r["wall_s"] for r in rows]),
        "reason_tok": _mean([r["total_reasoning_tokens"] for r in rows]),
        "out_tok": _mean([r["total_completion_tokens"] for r in rows]),
        "in_tok": _mean([r["total_prompt_tokens"] for r in rows]),
        "cache_hit": _mean([r.get("prefix_cache_hit_rate") for r in rows]),
        "forced": sum(r["status"] == "submitted_forced" for r in rows),
        "failed_status": sum(not r["status"].startswith("submitted") for r in rows),
        # Cost inputs are per SUCCESSFUL task, so total spend is divided by successes.
        "wall_s_per_success": sum(r["wall_s"] for r in rows) / len(ok) if ok else float("nan"),
        "out_tok_per_success": sum(r["total_completion_tokens"] for r in rows) / len(ok) if ok else float("nan"),
        "in_tok_per_success": sum(r["total_prompt_tokens"] for r in rows) / len(ok) if ok else float("nan"),
        "cached_tok_per_success": sum(r["total_cached_tokens"] or 0 for r in rows) / len(ok) if ok else float("nan"),
    }
    return s


def breakdown(rows, key):
    groups = defaultdict(list)
    for r in rows:
        groups[r["truth"][key]].append(r)
    order = {"easy": 0, "medium": 1, "hard": 2}
    return {k: summarize(v) for k, v in sorted(groups.items(), key=lambda kv: (order.get(kv[0], 9), kv[0]))}


def print_one(name, rows):
    s = summarize(rows)
    print(f"\n=== {name}: {s['success']}/{s['cases']} correct ({s['success_rate']:.0%})")
    print(f"    type {s['type_acc']:.0%}  file {s['file_acc']:.0%}  column {s['col_acc']:.0%}   "
          f"forced submits {s['forced']}  no answer {s['failed_status']}")
    print(f"    per case: {s['steps']:.1f} steps, {s['wall_s']:.0f}s, {s['reason_tok']:.0f} reasoning tok, "
          f"{s['out_tok']:.0f} out tok, {s['in_tok']:.0f} in tok, cache hit {s['cache_hit']:.0%}")
    print(f"    per SUCCESS: {s['wall_s_per_success']:.0f}s, {s['out_tok_per_success']:.0f} out tok, "
          f"{s['in_tok_per_success']:.0f} in tok ({s['cached_tok_per_success']:.0f} cached)")

    for key in ("tier", "failure_type"):
        print(f"\n    by {key}:")
        for k, g in breakdown(rows, key).items():
            print(f"      {k:<19} {g['success']}/{g['cases']}  {g['steps']:4.1f} steps  "
                  f"{g['wall_s']:4.0f}s  {g['reason_tok']:5.0f} reason tok")

    statuses = defaultdict(int)
    for r in rows:
        statuses[r["status"]] += 1
    print(f"\n    statuses: {dict(statuses)}")


def print_cases(rows):
    print(f"\n{'case':<9} {'truth':<34} {'predicted':<34} {'ok':<3} {'steps':>5} {'sec':>5} {'reason':>6}  status")
    for r in sorted(rows, key=lambda r: r["case_id"]):
        t, p = r["truth"], r.get("prediction") or {}
        truth = f"{t['failure_type']}:{Path(t['file']).stem}.{t['column']}"
        pred = f"{p.get('failure_type')}:{Path(p.get('file') or '').stem}.{p.get('column')}" if p else "-"
        print(f"{r['case_id']:<9} {truth:<34} {pred:<34} {'Y' if r['success'] else '.':<3} "
              f"{r['n_steps']:>5} {r['wall_s']:>5.0f} {r['total_reasoning_tokens'] or 0:>6}  {r['status']}")


def print_compare(runs):
    cols = ["success_rate", "steps", "wall_s", "reason_tok", "out_tok", "cache_hit",
            "wall_s_per_success", "out_tok_per_success"]
    fmt = {"success_rate": "{:.0%}", "cache_hit": "{:.0%}", "steps": "{:.1f}"}
    print(f"\n{'run':<22} {'n':>3} " + " ".join(f"{c:>12}" for c in cols))
    for name, rows in runs.items():
        s = summarize(rows)
        print(f"{name:<22} {s['cases']:>3} " +
              " ".join(f"{fmt.get(c, '{:.0f}').format(s[c]):>12}" for c in cols))
    # success by tier side by side
    tiers = ["easy", "medium", "hard"]
    print(f"\n{'run':<22} " + " ".join(f"{t:>10}" for t in tiers))
    for name, rows in runs.items():
        b = breakdown(rows, "tier")
        print(f"{name:<22} " + " ".join(
            f"{b[t]['success']}/{b[t]['cases']:>3}".rjust(10) if t in b else "-".rjust(10) for t in tiers))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--labels", default="cases/labels.jsonl")
    ap.add_argument("--cases-only", action="store_true")
    ap.add_argument("--json", help="write per-run summaries to this file (for the dashboard)")
    a = ap.parse_args()

    labels = load_labels(a.labels)
    runs = {Path(p).stem: load_run(p, labels) for p in a.runs}
    runs = {k: v for k, v in runs.items() if v}
    if not runs:
        sys.exit("no graded cases found")

    if a.cases_only:
        for name, rows in runs.items():
            print(f"\n### {name}")
            print_cases(rows)
    elif len(runs) == 1:
        name, rows = next(iter(runs.items()))
        print_one(name, rows)
        print_cases(rows)
    else:
        print_compare(runs)

    if a.json:
        out = {name: {"overall": summarize(rows), "by_tier": breakdown(rows, "tier"),
                      "by_type": breakdown(rows, "failure_type")} for name, rows in runs.items()}
        Path(a.json).write_text(json.dumps(out, indent=2))
        print(f"\nwrote {a.json}")


if __name__ == "__main__":
    main()
