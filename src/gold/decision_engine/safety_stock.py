
import logging

import numpy as np
import pandas as pd
from scipy import stats
from sqlalchemy import create_engine, text, inspect

logger = logging.getLogger(__name__)

SERVICE_LEVEL = 0.95
Z_SCORE = stats.norm.ppf(SERVICE_LEVEL)  # ~1.645 for 95%


def _assert_sources_exist(engine) -> None:
    inspector = inspect(engine)
    silver_tables = inspector.get_table_names(schema="silver")
    missing = [t for t in ("orders", "supplier_leadtime_params") if t not in silver_tables]
    if missing:
        raise RuntimeError(
            f"Missing required silver table(s): {missing}. Run clean_orders.py "
            "and leadtime_distribution.py (via silver_processing DAG) first."
        )


def _fetch_weekly_demand_stats(engine) -> pd.DataFrame:
    """
    Per-SKU weekly demand mean and variance, computed from actual historical
    order data (not the point-forecast in silver.demand_forecast -- safety
    stock needs observed variability, not a single predicted value).
    """
    query = text("""
        WITH weekly AS (
            SELECT
                sku,
                date_trunc('week', order_date)::date AS week_start,
                SUM(order_item_quantity) AS qty
            FROM silver.orders
            GROUP BY sku, date_trunc('week', order_date)::date
        )
        SELECT
            sku,
            AVG(qty) AS mean_weekly_demand,
            VARIANCE(qty) AS var_weekly_demand,
            COUNT(*) AS weeks_observed
        FROM weekly
        GROUP BY sku
    """)
    return pd.read_sql(query, engine)


def _derive_primary_supplier_per_sku(engine) -> pd.DataFrame:
    """
    No clean sku -> supplier dimension exists. Derive one by taking the
    mode (most frequent) supplier_id per sku from PO line history.
    See module docstring for the limitations of this approximation.
    """
    query = text("""
        SELECT sku, supplier_id, COUNT(*) AS line_count
        FROM bronze.bronze_purchase_orders
        GROUP BY sku, supplier_id
    """)
    counts = pd.read_sql(query, engine)
    if counts.empty:
        return counts

    counts = counts.sort_values(["sku", "line_count", "supplier_id"], ascending=[True, False, True])
    primary = counts.drop_duplicates(subset="sku", keep="first")[["sku", "supplier_id"]]
    return primary


def _fetch_leadtime_params(engine) -> pd.DataFrame:
    query = text("""
        SELECT supplier_id,mean_lead_time_days,stddev_lead_time_days,
               distribution_type, sample_size
        FROM silver.supplier_leadtime_params
    """)
    return pd.read_sql(query, engine)


def _compute_safety_stock(
    demand_stats: pd.DataFrame,
    sku_supplier_map: pd.DataFrame,
    leadtime_params: pd.DataFrame,
) -> pd.DataFrame:
    merged = demand_stats.merge(sku_supplier_map, on="sku", how="inner")
    before = len(merged)
    merged = merged.merge(leadtime_params, on="supplier_id", how="inner")
    after = len(merged)

    excluded = before - after
    if excluded:
        logger.warning(
            "%d SKUs excluded: had demand history and a derived primary "
            "supplier, but that supplier has no fitted lead-time params.",
            excluded,
        )

    # Convert lead time from days to weeks to match weekly demand grain.
    merged["mean_lead_time_weeks"] = merged["mean_lead_time_days"] / 7.0
    merged["var_lead_time_weeks"] = (merged["stddev_lead_time_days"] / 7.0) ** 2

    merged["var_weekly_demand"] = merged["var_weekly_demand"].fillna(0.0)

    # SS = Z * sqrt( E[LT] * Var(D) + E[D]^2 * Var(LT) )
    term1 = merged["mean_lead_time_weeks"] * merged["var_weekly_demand"]
    term2 = (merged["mean_weekly_demand"] ** 2) * merged["var_lead_time_weeks"]
    merged["safety_stock_units"] = Z_SCORE * np.sqrt(term1 + term2)
    merged["safety_stock_units"] = merged["safety_stock_units"].round(1)

    merged["service_level"] = SERVICE_LEVEL
    merged["low_confidence_leadtime"] = merged["distribution_type"] == "insufficient_data_moments"

    return merged


def _write(engine, df: pd.DataFrame) -> None:
    output_cols = [
        "sku", "supplier_id", "mean_weekly_demand", "var_weekly_demand",
        "weeks_observed", "mean_lead_time_days", "stddev_lead_time_days",
        "safety_stock_units", "service_level", "low_confidence_leadtime",
    ]
    output = df[output_cols].copy()
    output["built_at"] = pd.Timestamp.now()
    output.to_sql("safety_stock", engine, schema="gold", if_exists="replace", index=False)
    logger.info("Wrote %d SKU safety stock rows to gold.safety_stock", len(output))


def build_safety_stock(conn_str: str) -> dict:
    engine = create_engine(conn_str)
    _assert_sources_exist(engine)

    demand_stats = _fetch_weekly_demand_stats(engine)
    if demand_stats.empty:
        raise ValueError("No weekly demand stats computed -- check silver.orders has data.")

    sku_supplier_map = _derive_primary_supplier_per_sku(engine)
    if sku_supplier_map.empty:
        raise ValueError(
            "No sku->supplier mapping could be derived from "
            "bronze.bronze_purchase_orders -- check it has data."
        )

    leadtime_params = _fetch_leadtime_params(engine)
    if leadtime_params.empty:
        raise ValueError(
            "silver.supplier_leadtime_params is empty -- run leadtime_distribution.py first."
        )

    result = _compute_safety_stock(demand_stats, sku_supplier_map, leadtime_params)
    if result.empty:
        raise ValueError(
            "No SKUs had both demand history and a matched supplier lead-time "
            "profile -- cannot compute any safety stock values."
        )

    _write(engine, result)

    summary = {
        "skus_with_demand_history": len(demand_stats),
        "skus_with_derived_supplier": len(sku_supplier_map),
        "skus_scored": len(result),
        "skus_low_confidence_leadtime": int(result["low_confidence_leadtime"].sum()),
        "mean_safety_stock_units": round(result["safety_stock_units"].mean(), 1),
    }
    logger.info("safety_stock summary: %s", summary)
    return summary


def run(conn_str: str, **context) -> dict:
    return build_safety_stock(conn_str)


if __name__ == "__main__":
    import os
    logging.basicConfig(level=logging.INFO)
    conn_str = os.environ.get(
        "WAREHOUSE_CONN_STRING",
        "postgresql+psycopg2://warehouse_admin:CHANGEME@postgres_warehouse:5432/resilience_radar",
    )
    print(run(conn_str))