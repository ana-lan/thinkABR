"""Phase 2.3: generate the 40 graded test cases.

Layout:
  cases/case_000/raw/*.csv      what the agent can inspect
  cases/case_000/jobs/*.sql
  cases/case_000/logs/run.log
  cases/case_000/alert.txt      the page the on-call agent receives
  cases/labels.jsonl            ground truth, kept OUTSIDE case dirs so tools can't read it

Usage: python pipeline/make_cases.py [--out cases] [--per-type 5]
"""
import argparse
import json
import random
import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.data import make_clean
from pipeline.injectors import FAILURE_TYPES, INJECTORS
from pipeline.jobs import run_pipeline

N_VARIANTS = {"missing_file": 3, "renamed_column": 5, "type_mismatch": 4, "date_format_change": 3,
              "duplicate_keys": 2, "null_explosion": 2, "bad_join_key": 3, "unit_change": 2}

# Expected difficulty, for analysis only. The router never sees this.
TIER = {"missing_file": "easy", "type_mismatch": "easy", "date_format_change": "easy",
        "renamed_column": "medium",
        "duplicate_keys": "hard", "null_explosion": "hard", "bad_join_key": "hard", "unit_change": "hard"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="cases")
    ap.add_argument("--per-type", type=int, default=5)
    args = ap.parse_args()

    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    specs = [(ft, k) for ft in FAILURE_TYPES for k in range(args.per_type)]
    random.Random(7).shuffle(specs)  # interleave types so a partial run still covers all of them

    labels = []
    for i, (ftype, k) in enumerate(specs):
        case_id = f"case_{i:03d}"
        seed = 1000 + i
        variant = k % N_VARIANTS[ftype]
        dfs = make_clean(seed)
        label = INJECTORS[ftype](dfs, np.random.default_rng(seed), variant)

        cdir = out / case_id
        (cdir / "raw").mkdir(parents=True)
        for name, df in dfs.items():
            if df is not None:
                df.to_csv(cdir / "raw" / f"{name}.csv", index=False)

        ok, failed_job = run_pipeline(cdir)
        assert not ok, f"{case_id} ({ftype} v{variant}) did not fail"

        (cdir / "alert.txt").write_text(
            f"PagerDuty: DAG daily_revenue failed on run 2026-11-03T02:00:00.\n"
            f"Failed task: {failed_job}. Downstream tasks were skipped.\n"
            f"Find the root cause (which input file and column) and propose a fix.\n")

        labels.append({"case_id": case_id, "seed": seed, "variant": variant,
                       "failed_job": failed_job, "tier": TIER[ftype], **label})
        print(f"{case_id}  {ftype:<19} v{variant}  {TIER[ftype]:<6}  {label['file']:<18} "
              f"{str(label['column']):<12} failed_at={failed_job}")

    with open(out / "labels.jsonl", "w") as f:
        for l in labels:
            f.write(json.dumps(l) + "\n")

    counts = {ft: sum(l["failure_type"] == ft for l in labels) for ft in FAILURE_TYPES}
    tiers = {t: sum(l["tier"] == t for l in labels) for t in ["easy", "medium", "hard"]}
    print(f"\n{len(labels)} cases written to {out}/  per type: {counts}  tiers: {tiers}")


if __name__ == "__main__":
    main()
