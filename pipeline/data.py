"""Clean synthetic source data for the triage pipeline.

Three raw CSVs: orders, customers, products. Deterministic given a seed.
"""
import numpy as np
import pandas as pd

REGIONS = ["north", "south", "east", "west", "central"]
CATEGORIES = ["electronics", "grocery", "apparel", "home", "toys", "books"]


def make_clean(seed: int, n_orders: int = 300, n_customers: int = 60, n_products: int = 25):
    rng = np.random.default_rng(seed)

    customers = pd.DataFrame({
        "customer_id": np.arange(1001, 1001 + n_customers),
        "name": [f"cust_{i:03d}" for i in range(n_customers)],
        "region": rng.choice(REGIONS, n_customers),
        "signup_date": pd.to_datetime("2025-01-01")
        + pd.to_timedelta(rng.integers(0, 600, n_customers), unit="D"),
    })
    customers["signup_date"] = customers["signup_date"].dt.strftime("%Y-%m-%d")

    products = pd.DataFrame({
        "product_id": np.arange(501, 501 + n_products),
        "name": [f"prod_{i:03d}" for i in range(n_products)],
        "category": rng.choice(CATEGORIES, n_products),
        "unit_price": np.round(rng.uniform(3, 120, n_products), 2),
    })

    prod_idx = rng.integers(0, n_products, n_orders)
    qty = rng.integers(1, 5, n_orders)
    ts = pd.to_datetime("2026-11-01") + pd.to_timedelta(rng.integers(0, 2 * 86400, n_orders), unit="s")
    orders = pd.DataFrame({
        "order_id": np.arange(90001, 90001 + n_orders),
        "customer_id": rng.choice(customers["customer_id"].to_numpy(), n_orders),
        "product_id": products["product_id"].to_numpy()[prod_idx],
        "qty": qty,
        "amount": np.round(products["unit_price"].to_numpy()[prod_idx] * qty, 2),
        "order_ts": ts.strftime("%Y-%m-%d %H:%M:%S"),
    })

    return {"orders": orders, "customers": customers, "products": products}
