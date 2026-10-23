"""Generates bronze_inventory_snapshots. Grain: one row per SKU x location x day.

Uses a simple day-by-day stock simulation (not pure random draws per day) so
that on_hand/backorder values are internally CONSISTENT over time -- stock
depletes with simulated daily demand and replenishes on a reorder trigger.
This matters: the safety-stock model (Model 4) needs realistic, autocorrelated
inventory trajectories, not independent noise per day.
"""

import numpy as np
import pandas as pd

def generate_inventory_snapshots(products_df: pd.DataFrame, n_locations: int,
                                  start_date: str, end_date: str,
                                  initial_stock_days_of_supply: int, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start_date, end_date, freq="D")
    locations = [f"LOC-{i:02d}" for i in range(n_locations)]

    rows = []
    for sku in products_df["sku"].sample(n=min(150, len(products_df)), random_state=seed):  # subset for volume control
        for loc in locations:
            avg_daily_demand = max(1, rng.poisson(10))
            reorder_point = avg_daily_demand * 7
            reorder_qty = avg_daily_demand * 21
            on_hand = avg_daily_demand * initial_stock_days_of_supply
            on_order = 0
            lead_time_days = rng.integers(5, 20)
            pending_delivery = {}   # date -> qty

            for d in dates:
                demand_today = rng.poisson(avg_daily_demand)
                available = on_hand
                on_hand = max(0, on_hand - demand_today)
                backorder = max(0, demand_today - available)

                if d in pending_delivery:
                    delivered   = pending_delivery.pop(d)
                    on_hand += delivered
                    on_order -= delivered

                if on_hand + on_order <= reorder_point:
                    arrival = d + pd.Timedelta(days=int(lead_time_days))
                    pending_delivery[arrival] = pending_delivery.get(arrival, 0) + reorder_qty
                    on_order += reorder_qty

                rows.append({
                    "snapshot_date": d, "sku": sku, "location_id": loc,
                    "location_type": rng.choice(["DC", "Plant", "Store"]),
                    "on_hand_qty": on_hand, "on_order_qty": max(0, on_order),
                    "backorder_qty": backorder, "safety_stock_target_qty": reorder_point,
                })

    return pd.DataFrame(rows)