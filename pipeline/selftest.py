"""Sanity check for 2.2: clean data passes, every injector variant fails, and prints the error line."""
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.data import make_clean
from pipeline.injectors import INJECTORS
from pipeline.jobs import run_pipeline

VARIANTS = {"missing_file": 3, "renamed_column": 5, "type_mismatch": 4, "date_format_change": 3,
            "duplicate_keys": 2, "null_explosion": 2, "bad_join_key": 3, "unit_change": 2}


def write_case(case_dir, dfs):
    raw = case_dir / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    for name, df in dfs.items():
        if df is not None:
            df.to_csv(raw / f"{name}.csv", index=False)


root = Path(tempfile.mkdtemp())
ok, failed = run_pipeline(root / "clean", ) if write_case(root / "clean", make_clean(0)) is None else None
print(f"clean: ok={ok}")
assert ok, (root / "clean/logs/run.log").read_text()

bad = 0
for ftype, nv in VARIANTS.items():
    for v in range(nv):
        dfs = make_clean(42 + v)
        label = INJECTORS[ftype](dfs, np.random.default_rng(v), v)
        cdir = root / f"{ftype}_{v}"
        write_case(cdir, dfs)
        ok, failed = run_pipeline(cdir)
        err = next((l for l in (cdir / "logs/run.log").read_text().splitlines() if " ERROR " in l), "")
        flag = "OK " if not ok else "!! "
        bad += ok
        print(f"{flag}{ftype:<19} v{v} {label['file']:<18} {str(label['column']):<12} failed_at={failed}")
        print(f"     {err[30:200]}")
shutil.rmtree(root)
print("ALL INJECTORS FAIL" if bad == 0 else f"{bad} VARIANTS DID NOT FAIL")
