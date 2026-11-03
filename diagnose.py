import json, math
from collections import Counter
import grade

LEVELS = ["low", "medium", "high", "xhigh"]
CTX = 8192
DIFF = {"missing_file": "easy", "type_mismatch": "easy", "date_format_change": "easy",
        "renamed_column": "medium"}
labels = grade.load_labels("cases/labels.jsonl")

def load(level):
    rows = grade.load_run(f"runs/fixed_{level}.jsonl", labels)
    return {r["case_id"]: r for r in rows}

def ftype(r): return r["truth"]["failure_type"]
def diff(r): return DIFF.get(ftype(r), "hard")

def max_prompt(r):
    best = None
    for v in r.values():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            for s in v:
                for sk, sv in s.items():
                    if "prompt" in sk and isinstance(sv, (int, float)):
                        best = max(best or 0, sv)
    return best

def nsteps(r):
    for k in ("steps_used", "n_steps", "num_steps"):
        if isinstance(r.get(k), int): return r[k]
    return len(r["steps"]) if isinstance(r.get("steps"), list) else None

def kind(r):
    st = r["status"]
    if not st.startswith("submitted"): return "error:" + st
    if r["success"]: return "ok"
    if not r["type_ok"]: return "wrong_type"
    if not r["file_ok"]: return "wrong_file"
    return "wrong_col"

def pred(r):
    p = r.get("prediction") or {}
    return f"{p.get('failure_type')}/{p.get('file')}/{p.get('column')}"

def mcnemar(b, c):
    n = b + c
    if n == 0: return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)

runs = {lv: load(lv) for lv in LEVELS}
ids = sorted(runs["low"])
r0 = runs["low"][ids[0]]
print("record keys:", sorted(r0))
print("steps field:", nsteps(r0), "| max_prompt field:", max_prompt(r0))

print("\n== 1. failure kinds per level ==")
for lv in LEVELS:
    rs = runs[lv].values()
    c = Counter(kind(r) for r in rs)
    f = [r for r in rs if r["status"] == "submitted_forced"]
    print(f"{lv:7} {dict(c)}  forced={len(f)} (correct {sum(r['success'] for r in f)})")

print("\n== 2. correct per failure type (out of 5) ==")
types = sorted({ftype(r) for r in runs["low"].values()}, key=lambda t: (["easy","medium","hard"].index(DIFF.get(t,"hard")), t))
print(f"{'type':20}" + "".join(f"{lv:>8}" for lv in LEVELS))
for t in types:
    print(f"{t:20}" + "".join(f"{sum(r['success'] for r in runs[lv].values() if ftype(r)==t):>8}" for lv in LEVELS))

print("\n== 3. paired diffs vs low (McNemar exact) ==")
for lv in ["high", "medium", "xhigh"]:
    a = [i for i in ids if runs["low"][i]["success"] and not runs[lv][i]["success"]]
    b = [i for i in ids if runs[lv][i]["success"] and not runs["low"][i]["success"]]
    print(f"low vs {lv}: low-only={len(a)} {lv}-only={len(b)} p={mcnemar(len(a), len(b)):.3f}")
    for i in a:
        r = runs[lv][i]
        print(f"   {lv} missed {i} [{ftype(r)}] {kind(r)} {r['status']} steps={nsteps(r)} pred={pred(r)}")
    for i in b:
        r = runs["low"][i]
        print(f"   low missed {i} [{ftype(r)}] {kind(r)} {r['status']} steps={nsteps(r)} pred={pred(r)}")

print(f"\n== 4. context pressure (limit {CTX}) ==")
for lv in LEVELS:
    rs = list(runs[lv].values())
    mp = [(max_prompt(r), r["success"]) for r in rs if max_prompt(r) is not None]
    if not mp:
        print(f"{lv:7} no per-step prompt tokens; max total_prompt_tokens={max(r['total_prompt_tokens'] for r in rs)}"); continue
    near = [s for m, s in mp if m > CTX - 1500]
    print(f"{lv:7} max={max(m for m,_ in mp)} mean={sum(m for m,_ in mp)/len(mp):.0f} cases>{CTX-1500}={len(near)} failed_among_them={near.count(False)}")

print("\n== 5. hard cases: steps ==")
for lv in LEVELS:
    st = [nsteps(r) for r in runs[lv].values() if diff(r) == "hard"]
    st = [s for s in st if s is not None]
    if st: print(f"{lv:7} mean={sum(st)/len(st):.1f} at14={sum(s>=14 for s in st)}")
