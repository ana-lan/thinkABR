"""Phase 2.4: the triage agent's tools.

Five investigation tools plus submit_diagnosis (the structured final answer).
Every tool returns a string, never raises, and is capped so the 8K context survives
a full investigation. The agent can only see files under the case's raw/, jobs/, logs/.
"""
import json
import re
from pathlib import Path

import duckdb

from pipeline.injectors import FAILURE_TYPES
from pipeline.jobs import JOB_ORDER, JOBS

MAX_CHARS = 1500      # hard cap per tool result (~400 to 500 tokens)
MAX_ROWS = 20         # sample_rows / run_sql row cap
MAX_LINE = 400        # per-line cap inside a result
TABLES = ["orders", "customers", "products"]

TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "read_error_log",
        "description": "Read the log of the failed pipeline run: task order, row counts, and the error.",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "read_job_code",
        "description": f"Read the SQL of one pipeline job. Jobs in run order: {', '.join(JOB_ORDER)}.",
        "parameters": {"type": "object", "properties": {
            "job": {"type": "string", "enum": JOB_ORDER}}, "required": ["job"]}}},
    {"type": "function", "function": {
        "name": "get_schema",
        "description": "Show the columns, auto-detected types and row count of a raw input file. "
                       "Call with no file to list the raw files that exist.",
        "parameters": {"type": "object", "properties": {
            "file": {"type": "string", "description": "e.g. orders.csv"}}, "required": []}}},
    {"type": "function", "function": {
        "name": "sample_rows",
        "description": f"Show the first n rows (max {MAX_ROWS}) of a raw input file as CSV.",
        "parameters": {"type": "object", "properties": {
            "file": {"type": "string", "description": "e.g. customers.csv"},
            "n": {"type": "integer", "default": 5}}, "required": ["file"]}}},
    {"type": "function", "function": {
        "name": "run_sql",
        "description": "Run a read-only DuckDB query. Raw files are views named orders, customers, "
                       "products (types auto-detected). Pipeline tables that built successfully before "
                       "the failure (stg_*, int_orders_enriched) are also available. "
                       f"Returns at most {MAX_ROWS} rows.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "submit_diagnosis",
        "description": "Submit the final root cause and fix. Call this exactly once, when done.",
        "parameters": {"type": "object", "properties": {
            "failure_type": {"type": "string", "enum": FAILURE_TYPES},
            "file": {"type": "string", "description": "Raw file holding the root cause, e.g. orders.csv"},
            "column": {"type": "string", "description": "Column holding the root cause, or 'none' "
                                                       "if the whole file is the problem"},
            "fix": {"type": "string", "description": "Concrete fix in 1 to 3 sentences"}},
            "required": ["failure_type", "file", "column", "fix"]}}},
]

_BLOCKED_SQL = re.compile(
    r"\b(copy|export|attach|detach|install|load|pragma|set|call|checkpoint|"
    r"read_text|read_blob|glob|read_json\w*|read_parquet|write\w*)\b", re.I)


def _cap(text, limit=MAX_CHARS):
    lines = [l if len(l) <= MAX_LINE else l[:MAX_LINE] + " ...[line cut]" for l in text.splitlines()]
    text = "\n".join(lines)
    if len(text) > limit:
        text = text[:limit] + f"\n...[truncated, {len(text) - limit} more chars]"
    return text


def _table_name(file):
    name = Path(str(file).strip()).name.removesuffix(".csv").lower()
    return name if name in TABLES else None


class CaseTools:
    def __init__(self, case_dir):
        self.case = Path(case_dir).resolve()
        self._con = None

    # ---------- dispatch ----------
    def call(self, name, arguments):
        try:
            args = json.loads(arguments) if isinstance(arguments, str) else (arguments or {})
        except json.JSONDecodeError:
            return f"ERROR: arguments are not valid JSON: {arguments[:200]}"
        fn = getattr(self, f"t_{name}", None)
        if fn is None or name == "submit_diagnosis":
            return f"ERROR: unknown tool {name}"
        try:
            return _cap(fn(**args))
        except TypeError as e:
            return f"ERROR: bad arguments for {name}: {e}"
        except Exception as e:  # tool bugs must not kill the run
            return f"ERROR: {type(e).__name__}: {e}"

    # ---------- tools ----------
    def t_read_error_log(self, **_):
        return (self.case / "logs" / "run.log").read_text()

    def t_read_job_code(self, job, **_):
        if job not in JOBS:
            return f"ERROR: no job named {job}. Jobs: {', '.join(JOB_ORDER)}"
        return (self.case / "jobs" / f"{job}.sql").read_text()

    def _existing(self):
        return sorted(p.name for p in (self.case / "raw").glob("*.csv"))

    def t_get_schema(self, file=None, **_):
        files = self._existing()
        if not file:
            return "raw files: " + (", ".join(files) or "(none)")
        t = _table_name(file)
        if t is None or f"{t}.csv" not in files:
            return f"ERROR: raw/{Path(str(file)).name} does not exist. Existing raw files: {', '.join(files)}"
        con = duckdb.connect()
        path = str(self.case / "raw" / f"{t}.csv")
        rows = con.execute(f"DESCRIBE SELECT * FROM read_csv_auto('{path}')").fetchall()
        n = con.execute(f"SELECT COUNT(*) FROM read_csv_auto('{path}')").fetchone()[0]
        con.close()
        cols = "\n".join(f"  {r[0]}: {r[1]}" for r in rows)
        return f"raw/{t}.csv  rows={n}\n{cols}"

    def t_sample_rows(self, file, n=5, **_):
        t = _table_name(file)
        files = self._existing()
        if t is None or f"{t}.csv" not in files:
            return f"ERROR: raw/{Path(str(file)).name} does not exist. Existing raw files: {', '.join(files)}"
        n = max(1, min(int(n), MAX_ROWS))
        with open(self.case / "raw" / f"{t}.csv") as f:
            lines = [next(f, "") for _ in range(n + 1)]
        return "".join(l for l in lines if l).rstrip()

    def _conn(self):
        """In-memory DuckDB with raw views and every pipeline table that builds cleanly."""
        if self._con is not None:
            return self._con
        con = duckdb.connect()
        raw = str(self.case / "raw")
        for t in TABLES:
            if (self.case / "raw" / f"{t}.csv").exists():
                con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_csv_auto('{raw}/{t}.csv')")
        for job in JOB_ORDER:
            try:
                con.execute(JOBS[job].replace("'raw/", f"'{raw}/"))
            except duckdb.Error:
                pass  # failed or upstream-failed: table just won't exist
        self._con = con
        return con

    def t_run_sql(self, query, **_):
        q = str(query).strip().rstrip(";")
        if ";" in q:
            return "ERROR: one statement per call"
        if not re.match(r"(?is)^\s*(select|with|describe|show|summarize|from)\b", q):
            return "ERROR: read-only queries only (SELECT / WITH / DESCRIBE / SUMMARIZE)"
        if _BLOCKED_SQL.search(q):
            return "ERROR: that function or statement is not allowed"
        for lit in re.findall(r"'([^']*)'", q):  # file paths must stay inside raw/
            if "/" in lit or ".." in lit or lit.endswith((".csv", ".json", ".jsonl")):
                if not re.fullmatch(r"raw/(orders|customers|products)\.csv", lit):
                    return "ERROR: file access is limited to raw/orders.csv, raw/customers.csv, raw/products.csv"
        q = q.replace("'raw/", f"'{self.case / 'raw'}/")
        try:
            cur = self._conn().execute(q)
            cols = [d[0] for d in cur.description]
            rows = cur.fetchmany(MAX_ROWS + 1)
        except duckdb.Error as e:
            return f"SQL ERROR: {str(e).strip()}"
        more = len(rows) > MAX_ROWS
        rows = rows[:MAX_ROWS]
        out = [" | ".join(cols)] + [" | ".join("NULL" if v is None else str(v) for v in r) for r in rows]
        if more:
            out.append(f"...[more than {MAX_ROWS} rows, add LIMIT or aggregate]")
        if not rows:
            out.append("(0 rows)")
        return "\n".join(out)


def parse_submission(arguments):
    """Normalize submit_diagnosis args into a prediction dict for the grader."""
    try:
        a = json.loads(arguments) if isinstance(arguments, str) else dict(arguments)
    except json.JSONDecodeError:
        return None
    col = str(a.get("column", "")).strip().lower()
    t = _table_name(a.get("file", ""))
    return {
        "failure_type": str(a.get("failure_type", "")).strip(),
        "file": f"raw/{t}.csv" if t else str(a.get("file", "")).strip(),
        "column": None if col in ("", "none", "null", "n/a") else col,
        "fix": str(a.get("fix", "")).strip(),
    }
