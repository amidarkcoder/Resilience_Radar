"""Generates bronze_order_lifecycle_events. Grain: one row per order PER EVENT.

For each order, simulates a realistic sequence of milestone timestamps with
randomized gaps between stages -- this is the raw event stream that gold's
accumulating snapshot (fct_order_lifecycle) later collapses to one row/order.
"""

import numpy as np
import pandas as pd
from faker import Faker

EVENT_SEQUENCE = ["PLACED", "PICKED", "PACKED", "SHIPPED", "DELIVERED"]

def generate_order_lifecycle_events(orders_df: pd.DataFrame, return_rate: float = 0.04,
                                     seed: int = 42) -> pd.DataFrame:
    fake = Faker()
    rng = np.random.default_rng(seed)

    unique_orders = orders_df.drop_duplicates("order_id")[["order_id", "order_date", "days_for_shipment_scheduled"]]
    rows = []

    for _, order in unique_orders.iterrows():
        t = pd.Timestamp(order["order_date"])
        promised_date = t + pd.Timedelta(days=int(order["days_for_shipment_scheduled"]))

        # gaps between milestones -- gamma distributed, small positive skew
        gaps_hours = rng.gamma(shape=2.0, scale=6.0, size=len(EVENT_SEQUENCE) - 1)
        timestamps = [t]
        for gap in gaps_hours:
            timestamps.append(timestamps[-1] + pd.Timedelta(hours=gap))

        for event_type, ts in zip(EVENT_SEQUENCE, timestamps):
            rows.append({
                "event_id": fake.uuid4(),
                "order_id": order["order_id"],
                "event_type": event_type,
                "event_timestamp": ts,
                "event_location": fake.city(),
                "promised_date": promised_date.date(),
            })

        # small fraction of orders get a RETURNED event after delivery
        if rng.random() < return_rate:
            rows.append({
                "event_id": fake.uuid4(),
                "order_id": order["order_id"],
                "event_type": "RETURNED",
                "event_timestamp": timestamps[-1] + pd.Timedelta(days=int(rng.integers(1, 14))),
                "event_location": fake.city(),
                "promised_date": promised_date.date(),
            })

    return pd.DataFrame(rows)