"""Pipeline jobs (DuckDB SQL) plus data quality checks, and a runner that writes an Airflow-style log.

Run order: stg_orders, stg_customers, stg_products, int_orders_enriched, fct_daily_revenue.
The runner executes inside the case directory, so paths like raw/orders.csv are relative.
"""
import datetime as dt
import os
from pathlib import Path

import duckdb

JOBS = {
    "stg_orders": """\
-- Stage raw orders: read everything as text, then cast to typed columns.
CREATE OR REPLACE TABLE stg_orders AS
SELECT
    CAST(src.order_id    AS INTEGER)       AS order_id,
    CAST(src.customer_id AS INTEGER)       AS customer_id,
    CAST(src.product_id  AS INTEGER)       AS product_id,
    CAST(src.qty         AS INTEGER)       AS qty,
    CAST(src.amount      AS DECIMAL(12,2)) AS amount,
    CAST(src.order_ts    AS TIMESTAMP)     AS order_ts
FROM read_csv('raw/orders.csv', header = true, all_varchar = true) AS src;
""",
    "stg_customers": """\
-- Stage raw customers. customer_id is kept as text (CRM export), cast happens at join time.
CREATE OR REPLACE TABLE stg_customers AS
SELECT
    TRIM(src.customer_id)           AS customer_id,
    src.name,
    NULLIF(TRIM(src.region), '')    AS region,
    CAST(src.signup_date AS DATE)   AS signup_date
FROM read_csv('raw/customers.csv', header = true, all_varchar = true) AS src;
""",
    "stg_products": """\
-- Stage raw products. product_id is kept as text (catalog export), cast happens at join time.
CREATE OR REPLACE TABLE stg_products AS
SELECT
    TRIM(src.product_id)                  AS product_id,
    src.name,
    NULLIF(TRIM(src.category), '')        AS category,
    CAST(src.unit_price AS DECIMAL(10,2)) AS unit_price
FROM read_csv('raw/products.csv', header = true, all_varchar = true) AS src;
""",
    "int_orders_enriched": """\
-- One row per order, enriched with customer region and product category.
CREATE OR REPLACE TABLE int_orders_enriched AS
SELECT
    o.order_id,
    o.order_ts,
    o.qty,
    o.amount,
    c.customer_id AS c_customer_id,
    c.region,
    p.product_id  AS p_product_id,
    p.category
FROM stg_orders o
LEFT JOIN stg_customers c ON TRY_CAST(c.customer_id AS INTEGER) = o.customer_id
LEFT JOIN stg_products  p ON TRY_CAST(p.product_id  AS INTEGER) = o.product_id;
""",
    "fct_daily_revenue": """\
-- Daily revenue by region and category.
CREATE OR REPLACE TABLE fct_daily_revenue AS
SELECT
    CAST(order_ts AS DATE) AS order_date,
    region,
    category,
    COUNT(*)    AS n_orders,
    SUM(amount) AS revenue
FROM int_orders_enriched
GROUP BY ALL;
""",
}

JOB_ORDER = list(JOBS)


class DataQualityError(Exception):
    pass


def _scalar(con, sql):
    return con.execute(sql).fetchone()[0]


def check(job, con):
    """Data quality checks run after each job. Raise DataQualityError on failure."""
    if job == "stg_orders":
        n = _scalar(con, "SELECT COUNT(*) FROM stg_orders")
        if n == 0:
            raise DataQualityError("check row_count_nonzero failed on stg_orders: 0 rows")
    elif job == "int_orders_enriched":
        n_orders = _scalar(con, "SELECT COUNT(*) FROM stg_orders")
        n_enriched = _scalar(con, "SELECT COUNT(*) FROM int_orders_enriched")
        if n_enriched != n_orders:
            raise DataQualityError(
                f"check one_row_per_order failed on int_orders_enriched: "
                f"{n_enriched} rows vs {n_orders} rows in stg_orders")
        for col, side in [("c_customer_id", "customer"), ("p_product_id", "product")]:
            rate = _scalar(con, f"SELECT AVG(({col} IS NOT NULL)::INT) FROM int_orders_enriched")
            if rate < 0.95:
                raise DataQualityError(
                    f"check {side}_join_match_rate failed on int_orders_enriched: "
                    f"match rate {rate:.2f} < 0.95")
        for col in ["region", "category"]:
            rate = _scalar(con, f"SELECT AVG(({col} IS NULL)::INT) FROM int_orders_enriched")
            if rate > 0.05:
                raise DataQualityError(
                    f"check not_null_rate({col}) failed on int_orders_enriched: "
                    f"null rate {rate:.2f} > 0.05")
        aov = float(_scalar(con, "SELECT AVG(amount) FROM int_orders_enriched"))
        if not 5 <= aov <= 500:
            raise DataQualityError(
                f"check avg_order_value_in_range failed on int_orders_enriched: "
                f"avg amount {aov:.2f} outside [5, 500]")


def run_pipeline(case_dir, run_date="2026-11-03"):
    """Run all jobs inside case_dir. Writes jobs/*.sql and logs/run.log. Returns (ok, failed_job)."""
    case_dir = Path(case_dir)
    (case_dir / "jobs").mkdir(parents=True, exist_ok=True)
    (case_dir / "logs").mkdir(parents=True, exist_ok=True)
    for name, sql in JOBS.items():
        (case_dir / "jobs" / f"{name}.sql").write_text(sql)

    t = dt.datetime.fromisoformat(f"{run_date}T02:00:00")
    lines = []

    def log(level, msg):
        nonlocal t
        t += dt.timedelta(seconds=1)
        lines.append(f"[{t:%Y-%m-%d %H:%M:%S}] {level:<5} {msg}")

    log("INFO", f"dag=daily_revenue run_id=scheduled__{run_date}T02:00:00 starting")
    prev = os.getcwd()
    os.chdir(case_dir)
    con = duckdb.connect()
    failed = None
    try:
        for job in JOB_ORDER:
            log("INFO", f"task={job} state=running sql=jobs/{job}.sql")
            try:
                con.execute(JOBS[job])
                rows = _scalar(con, f"SELECT COUNT(*) FROM {job}")
                log("INFO", f"task={job} wrote {rows} rows")
                check(job, con)
                log("INFO", f"task={job} checks passed state=success")
            except (duckdb.Error, DataQualityError) as e:
                failed = job
                kind = type(e).__name__
                msg = str(e).strip().replace("\n", " | ")
                log("ERROR", f"task={job} {kind}: {msg}")
                log("ERROR", f"task={job} state=failed")
                for down in JOB_ORDER[JOB_ORDER.index(job) + 1:]:
                    log("WARN", f"task={down} state=upstream_failed")
                break
    finally:
        con.close()
        os.chdir(prev)

    log("INFO" if failed is None else "ERROR",
        f"dag=daily_revenue finished state={'success' if failed is None else 'failed'}")
    (case_dir / "logs" / "run.log").write_text("\n".join(lines) + "\n")
    return failed is None, failed
