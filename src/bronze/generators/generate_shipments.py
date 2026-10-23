"""Generates bronze_shipments. Grain: one row per outbound (customer-facing) shipment.

Depends on orders_df so ship_date/delivery_date stay consistent with the
order's actual order_date (no shipment before its order was placed).
"""

import numpy as np
import pandas as pd
from faker import Faker

def generate_shipments(orders_df: pd.DataFrame, carrier_names: list,
                        transit_days_lognormal: dict, seed: int = 42) -> pd.DataFrame:
    fake = Faker()
    rng = np.random.default_rng(seed)

    unique_orders = orders_df.drop_duplicates("order_id")[["order_id", "order_date", "shipping_mode"]]
    n = len(unique_orders)

    # Same-Day/First Class get shorter transit; mode-aware, not flat random
    mode_adjust = unique_orders["shipping_mode"].map({
        "Same Day": 0.3, "First Class": 0.6, "Second Class": 1.0, "Standard Class": 1.4
    }).fillna(1.0).values

    transit_days = np.round(
        rng.lognormal(mean=transit_days_lognormal["mean"], sigma=transit_days_lognormal["sigma"], size=n)
        * mode_adjust
    ).astype(int).clip(min=1)

    ship_dates = pd.to_datetime(unique_orders["order_date"]) + pd.to_timedelta(rng.integers(0, 2, size=n), unit="D")
    delivery_dates = ship_dates + pd.to_timedelta(transit_days, unit="D")

    df = pd.DataFrame({
        "shipment_id": [fake.uuid4() for _ in range(n)],
        "order_id": unique_orders["order_id"].values,
        "ship_date": ship_dates,
        "delivery_date": delivery_dates,
        "origin_location": [fake.city() for _ in range(n)],
        "destination_location": [fake.city() for _ in range(n)],
        "shipping_mode": unique_orders["shipping_mode"].values,
        "carrier_name": rng.choice(carrier_names, size=n),
        "freight_cost": np.round(rng.gamma(shape=2.5, scale=15, size=n), 2),
        "distance_km": np.round(rng.gamma(shape=3.0, scale=300, size=n), 1),
        "transit_days_actual": transit_days,
    })
    return df