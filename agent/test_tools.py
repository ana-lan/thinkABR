"""Sanity check for 2.4: every hard case is solvable with the tools, outputs stay small,
and the agent can't escape raw/ or read the labels."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent.tools import TOOL_SCHEMAS, CaseTools, parse_submission

CASES = Path(sys.argv[1] if len(sys.argv) > 1 else "cases")
labels = {l["case_id"]: l for l in map(json.loads, open(CASES / "labels.jsonl"))}
first = {}
for cid, l in labels.items():
    first.setdefault(l["failure_type"], cid)

# One "oracle" probe per failure type: the query a good agent would end up running.
PROBES = {
    "missing_file": [("get_schema", {"file": "{file}"})],
    "renamed_column": [("read_error_log", {}), ("get_schema", {"file": "{file}"})],
    "type_mismatch": [("get_schema", {"file": "{file}"})],
    "date_format_change": [("sample_rows", {"file": "{file}", "n": 3})],
    "duplicate_keys": [("run_sql", {"query": "SELECT {col}, COUNT(*) n FROM {t} GROUP BY 1 HAVING n > 1 LIMIT 5"})],
    "null_explosion": [("run_sql", {"query": "SELECT AVG(({col} IS NULL)::INT) null_rate FROM {t}"})],
    "bad_join_key": [("sample_rows", {"file": "{file}", "n": 3})],
    "unit_change": [("run_sql", {"query": "SELECT MIN(amount), AVG(amount), MAX(amount) FROM orders"})],
}

sizes = []
for ftype, cid in first.items():
    l = labels[cid]
    t = Path(l["file"]).stem
    tools = CaseTools(CASES / cid)
    print(f"\n===== {cid}  {ftype}  truth={l['file']}:{l['column']}")
    for name, args in PROBES[ftype]:
        args = {k: (v.format(file=f"{t}.csv", col=l["column"], t=t) if isinstance(v, str) else v)
                for k, v in args.items()}
        out = tools.call(name, json.dumps(args))
        sizes.append(len(out))
        print(f"--> {name}({args})  [{len(out)} chars]\n{out}")

# Every tool on every case: no crashes, sizes bounded.
for cid in labels:
    tools = CaseTools(CASES / cid)
    for name, args in [("read_error_log", {}), ("read_job_code", {"job": "int_orders_enriched"}),
                       ("get_schema", {"file": "orders.csv"}), ("sample_rows", {"file": "customers", "n": 50}),
                       ("run_sql", {"query": "SELECT * FROM orders"}),
                       ("run_sql", {"query": "SELECT COUNT(*) FROM int_orders_enriched"})]:
        out = tools.call(name, json.dumps(args))
        assert "Traceback" not in out, out
        sizes.append(len(out))

# Escapes must be blocked.
tools = CaseTools(CASES / "case_000")
print("\n===== escape attempts")
for q in ["SELECT * FROM read_csv_auto('../labels.jsonl')",
          "SELECT * FROM read_csv_auto('/etc/passwd')",
          "SELECT * FROM read_text('../labels.jsonl')",
          "COPY orders TO 'x.csv'",
          "SELECT 1; DROP TABLE orders"]:
    print(f"{q[:50]:<52} -> {tools.call('run_sql', json.dumps({'query': q}))}")
print("bad tool  ->", tools.call("rm_rf", "{}"))
print("bad json  ->", tools.call("run_sql", "{not json"))
print("bad args  ->", tools.call("read_job_code", '{"jobb": "x"}'))

print("\nparse_submission:", parse_submission(
    '{"failure_type":"bad_join_key","file":"raw/Customers.csv","column":"customer_id","fix":"strip prefix"}'))
print(f"\nschema tokens approx: {len(json.dumps(TOOL_SCHEMAS)) // 4}")
print(f"tool output chars: max={max(sizes)} mean={sum(sizes) // len(sizes)} over {len(sizes)} calls")
