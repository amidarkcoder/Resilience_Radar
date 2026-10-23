"""Generates bronze_purchase_orders. Grain: one row per supplier PO line.

KEY DESIGN CHOICE: lead-time reliability is tied to supplier_tier, not purely
random -- Tier 1 suppliers get tight, low-variance lead times; Tier 3 gets
wide, skewed lead times. This is what gives Model 1 (lead-time distribution
fitting) real signal to recover, instead of fitting noise.
"""

import numpy as np
import pandas as pd
from faker import Faker

def generate_purchase_orders(suppliers_df: pd.DataFrame, products_df: pd.DataFrame,
                              n_po_lines: int, start_date: str, end_date: str,
                              reliability_tiers: dict, incoterms: list,
                              freight_modes_weights: dict, seed: int = 42) -> pd.DataFrame:
    fake = Faker()
    rng = np.random.default_rng(seed)

    chosen_suppliers = suppliers_df.sample(n=n_po_lines, replace=True, random_state=seed).reset_index(drop=True)
    chosen_skus = rng.choice(products_df["sku"].values, size=n_po_lines)
    po_dates = pd.to_datetime(rng.choice(pd.date_range(start_date, end_date), size=n_po_lines))

    promised_lt, actual_lt = [], []
    for tier in chosen_suppliers["supplier_tier"]:
        params = reliability_tiers[tier]
        base = params["base_lt_days"]
        cv = params["cv"]
        promised = base
        # actual lead time = lognormal around promised, variance scaled by supplier tier's cv
        sigma = cv
        mu = np.log(base) - (sigma ** 2) / 2
        actual = rng.lognormal(mean=mu, sigma=sigma)
        promised_lt.append(promised)
        actual_lt.append(round(actual))

    promised_delivery = po_dates + pd.to_timedelta(promised_lt, unit="D")
    actual_delivery = po_dates + pd.to_timedelta(actual_lt, unit="D")

    # ~5% of POs are still open (not yet delivered) -- realistic, not an error
    still_open_mask = rng.random(n_po_lines) < 0.05
    actual_delivery = actual_delivery.where(~still_open_mask, pd.NaT)

    df = pd.DataFrame({
        "po_id": [fake.uuid4() for _ in range(n_po_lines)],
        "po_line_id": [fake.uuid4() for _ in range(n_po_lines)],
        "supplier_id": chosen_suppliers["supplier_id"].values,
        "sku": chosen_skus,
        "po_date": po_dates,
        "promised_delivery_date": promised_delivery,
        "actual_delivery_date": actual_delivery,
        "po_quantity": rng.integers(50, 2000, size=n_po_lines),
        "unit_cost_at_po": np.round(rng.lognormal(2.8, 0.6, size=n_po_lines), 2),
        "incoterm": rng.choice(incoterms, size=n_po_lines),
        "freight_mode": rng.choice(list(freight_modes_weights.keys()), size=n_po_lines,
                                    p=list(freight_modes_weights.values())),
        "origin_country": chosen_suppliers["supplier_country"].values,
        "destination_country": "USA",
        "po_status": np.where(still_open_mask, "OPEN", "CLOSED"),
    })
    return df