"""Generates bronze_orders. Grain: one row per order LINE ITEM.

Order-level attributes (customer, date, region, country, market, shipping
mode, promised delivery days, order status, late-delivery risk) are generated
once per ORDER and then expanded to the line-item grain, so that every line
item belonging to the same order_id shares consistent order-level values --
mirroring how a real order-line fact table works (one order, N SKUs).

Distributional choices mirror real retail data shape rather than uniform
randomness: Zipf-skewed SKU popularity (a few SKUs drive most volume),
Poisson order quantities and lines-per-order, Beta-distributed discounts.
"""

import numpy as np
import pandas as pd
from faker import Faker


def _zipf_weights(n: int) -> np.ndarray:
    weights = 1 / np.arange(1, n + 1)
    return weights / weights.sum()


def _expand_to_line_grain(order_grain_array: np.ndarray, lines_per_order: np.ndarray,
                           n_order_lines: int) -> np.ndarray:
    """Repeat an order-grain array to line-item grain (contiguous blocks, e.g.
    [A,A,A,B,B,C,...], NOT tiled), then truncate/pad to exactly n_order_lines
    so every column in the final DataFrame has identical length regardless of
    how the Poisson-distributed lines_per_order happens to sum up.
    """
    expanded = np.repeat(order_grain_array, lines_per_order)
    if len(expanded) >= n_order_lines:
        return expanded[:n_order_lines]
    pad = np.full(n_order_lines - len(expanded), expanded[-1])
    return np.concatenate([expanded, pad])


def generate_orders(customers_df: pd.DataFrame, products_df: pd.DataFrame,
                     n_order_lines: int, start_date: str, end_date: str,
                     quantity_poisson_lambda: int, discount_beta_params: list,
                     shipping_mode_weights: dict, order_status_weights: dict,
                     promised_days_weights: dict, markets: list, seed: int = 42) -> pd.DataFrame:
    fake = Faker()
    rng = np.random.default_rng(seed)

    # ---- ORDER-GRAIN generation --------------------------------------------
    # ~3 line items per order on average (Poisson + 1 so every order has >=1 line)
    avg_lines_per_order = 3
    n_orders = max(1, n_order_lines // avg_lines_per_order)
    lines_per_order = rng.poisson(lam=avg_lines_per_order, size=n_orders) + 1

    order_ids_distinct = np.array([fake.uuid4() for _ in range(n_orders)])
    order_customers = rng.choice(customers_df["customer_id"].values, size=n_orders)
    order_dates_distinct = pd.to_datetime(
        rng.choice(pd.date_range(start_date, end_date, freq="D"), size=n_orders)
    ).values
    order_regions = rng.choice(["North America", "LATAM", "EMEA", "APAC"], size=n_orders)
    order_countries = np.array([fake.country() for _ in range(n_orders)])
    order_markets = rng.choice(markets, size=n_orders)
    order_shipping_modes = rng.choice(list(shipping_mode_weights.keys()), size=n_orders,
                                       p=list(shipping_mode_weights.values()))
    order_promised_days = rng.choice(list(promised_days_weights.keys()), size=n_orders,
                                      p=list(promised_days_weights.values())).astype(int)
    order_statuses = rng.choice(list(order_status_weights.keys()), size=n_orders,
                                 p=list(order_status_weights.values()))

    # Late-delivery risk is NOT purely random -- it correlates with shipping_mode
    # and promised_days so Model 3 (the classifier) has real signal to learn,
    # not noise. Same-Day/short-promise orders are riskier. Computed at ORDER
    # grain since risk is a property of the shipment, not the individual SKU.
    risk_base = np.where(order_shipping_modes == "Same Day", 0.35,
                 np.where(order_shipping_modes == "Second Class", 0.25, 0.12))
    risk_base += np.where(order_promised_days == 2, 0.15, 0.0)
    order_late_delivery_risk = (rng.random(n_orders) < risk_base).astype(int).astype(str)

    # ---- Expand all order-grain arrays to LINE-ITEM grain ------------------
    order_ids = _expand_to_line_grain(order_ids_distinct, lines_per_order, n_order_lines)
    customer_ids = _expand_to_line_grain(order_customers, lines_per_order, n_order_lines)
    order_dates = _expand_to_line_grain(order_dates_distinct, lines_per_order, n_order_lines)
    order_regions_exp = _expand_to_line_grain(order_regions, lines_per_order, n_order_lines)
    order_countries_exp = _expand_to_line_grain(order_countries, lines_per_order, n_order_lines)
    order_markets_exp = _expand_to_line_grain(order_markets, lines_per_order, n_order_lines)
    shipping_modes = _expand_to_line_grain(order_shipping_modes, lines_per_order, n_order_lines)
    promised_days = _expand_to_line_grain(order_promised_days, lines_per_order, n_order_lines)
    order_statuses_exp = _expand_to_line_grain(order_statuses, lines_per_order, n_order_lines)
    late_delivery_risk = _expand_to_line_grain(order_late_delivery_risk, lines_per_order, n_order_lines)

    # ---- LINE-ITEM-GRAIN generation (genuinely varies per SKU within an order) ----
    skus = products_df["sku"].values
    sku_probs = _zipf_weights(len(skus))                       # skewed popularity
    sku_price_lookup = products_df.set_index("sku")["unit_price_msrp"]

    chosen_skus = rng.choice(skus, size=n_order_lines, p=sku_probs)
    quantities = rng.poisson(lam=quantity_poisson_lambda, size=n_order_lines) + 1
    discounts = np.round(rng.beta(*discount_beta_params, size=n_order_lines) * 30, 1)

    # price has realistic noise around catalog MSRP (promotions, regional variance)
    base_prices = sku_price_lookup.loc[chosen_skus].values
    unit_prices = np.round(base_prices * rng.normal(1.0, 0.05, size=n_order_lines), 2)

    df = pd.DataFrame({
        "order_id": order_ids,
        "order_item_id": [fake.uuid4() for _ in range(n_order_lines)],
        "order_date": order_dates,
        "customer_id": customer_ids,
        "sku": chosen_skus,
        "order_item_quantity": quantities,
        "order_item_unit_price": unit_prices,
        "order_item_discount_pct": discounts,
        "order_item_total": np.round(unit_prices * quantities * (1 - discounts / 100), 2),
        "order_status": order_statuses_exp,
        "shipping_mode": shipping_modes,
        "days_for_shipment_scheduled": promised_days,
        "order_region": order_regions_exp,
        "order_country": order_countries_exp,
        "market": order_markets_exp,
        "late_delivery_risk": late_delivery_risk,
    })

    return df