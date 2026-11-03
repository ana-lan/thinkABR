"""Failure injectors. Each takes the clean dataframes, an rng and a variant id,
mutates the data in place and returns the ground-truth label.

Label fields:
  failure_type  one of FAILURE_TYPES (what the agent must name)
  file          the raw file holding the root cause
  column        the column holding the root cause (None for missing_file)
  fix           reference fix text, used by the optional Spark grader
"""
import numpy as np
import pandas as pd

FAILURE_TYPES = [
    "missing_file",
    "renamed_column",
    "type_mismatch",
    "date_format_change",
    "duplicate_keys",
    "null_explosion",
    "bad_join_key",
    "unit_change",
]


def _label(ftype, table, column, fix):
    return {"failure_type": ftype, "file": f"raw/{table}.csv", "column": column, "fix": fix}


def missing_file(d, rng, v):
    table = ["orders", "customers", "products"][v % 3]
    d[table] = None
    return _label("missing_file", table, None,
                  f"Upstream export of {table}.csv did not land. Rerun or backfill the export, "
                  f"then add a file sensor before the staging task.")


def renamed_column(d, rng, v):
    table, old, new = [
        ("orders", "customer_id", "cust_id"),
        ("orders", "amount", "order_amount"),
        ("customers", "region", "sales_region"),
        ("products", "unit_price", "price"),
        ("orders", "order_ts", "created_at"),
    ][v % 5]
    d[table] = d[table].rename(columns={old: new})
    return _label("renamed_column", table, old,
                  f"Upstream renamed {old} to {new} in {table}.csv. Update stg_{table} to read {new} "
                  f"(aliased back to {old}) or ask the producer to restore the name.")


def type_mismatch(d, rng, v):
    table, col, bad = [
        ("orders", "amount", lambda x: f"${x}"),
        ("orders", "qty", lambda x: f"{x} pcs"),
        ("products", "unit_price", lambda x: str(x).replace(".", ",")),
        ("orders", "amount", lambda x: "N/A"),
    ][v % 4]
    df = d[table]
    df[col] = df[col].astype(str)
    frac = 0.03 if table == "orders" else 0.2
    idx = rng.choice(len(df), max(2, int(len(df) * frac)), replace=False)
    df.loc[df.index[idx], col] = [bad(x) for x in df[col].iloc[idx]]
    return _label("type_mismatch", table, col,
                  f"Some {col} values in {table}.csv are not numeric. Clean or reject the bad rows "
                  f"(TRY_CAST plus a quarantine table) and fix the upstream formatting.")


def date_format_change(d, rng, v):
    table, col, fmt = [
        ("orders", "order_ts", "%d/%m/%Y %H:%M"),
        ("customers", "signup_date", "%m-%d-%Y"),
        ("orders", "order_ts", "%Y%m%dT%H%M%S"),
    ][v % 3]
    d[table][col] = pd.to_datetime(d[table][col]).dt.strftime(fmt)
    return _label("date_format_change", table, col,
                  f"{col} in {table}.csv switched to format {fmt}. Parse it with strptime and that "
                  f"format in stg_{table}, or ask the producer to restore ISO 8601.")


def duplicate_keys(d, rng, v):
    table, key = [("customers", "customer_id"), ("products", "product_id")][v % 2]
    df = d[table]
    n = max(3, len(df) // 5)
    dup = df.sample(n=n, random_state=int(rng.integers(1e9)))
    d[table] = pd.concat([df, dup], ignore_index=True)
    d[table] = d[table].sample(frac=1, random_state=int(rng.integers(1e9))).reset_index(drop=True)
    return _label("duplicate_keys", table, key,
                  f"{table}.csv has duplicate {key} rows, so the join fans out. Deduplicate in "
                  f"stg_{table} (QUALIFY ROW_NUMBER() = 1) and add a uniqueness check on {key}.")


def null_explosion(d, rng, v):
    table, col = [("customers", "region"), ("products", "category")][v % 2]
    df = d[table]
    df[col] = df[col].astype(object)
    idx = rng.choice(len(df), int(len(df) * rng.uniform(0.4, 0.7)), replace=False)
    df.loc[df.index[idx], col] = ""
    return _label("null_explosion", table, col,
                  f"Most {col} values in {table}.csv are blank. Fix or backfill the upstream export, "
                  f"and keep the not-null check as a blocking gate.")


def bad_join_key(d, rng, v):
    table, key, fmt = [
        ("customers", "customer_id", lambda x: f"C-{x}"),
        ("products", "product_id", lambda x: f"SKU{x:06d}"),
        ("customers", "customer_id", lambda x: f"cust_{x}"),
    ][v % 3]
    d[table][key] = [fmt(int(x)) for x in d[table][key]]
    return _label("bad_join_key", table, key,
                  f"{key} in {table}.csv changed format, so TRY_CAST returns NULL and the join "
                  f"matches nothing. Strip the new prefix or format before casting, or fix upstream.")


def unit_change(d, rng, v):
    scale, unit = [(100, "cents"), (0.001, "thousands")][v % 2]
    d["orders"]["amount"] = np.round(d["orders"]["amount"] * scale, 4)
    return _label("unit_change", "orders", "amount",
                  f"orders.amount is now in {unit} instead of dollars. Convert it back in stg_orders "
                  f"and confirm the unit change with the producer.")


INJECTORS = {
    "missing_file": missing_file,
    "renamed_column": renamed_column,
    "type_mismatch": type_mismatch,
    "date_format_change": date_format_change,
    "duplicate_keys": duplicate_keys,
    "null_explosion": null_explosion,
    "bad_join_key": bad_join_key,
    "unit_change": unit_change,
}
