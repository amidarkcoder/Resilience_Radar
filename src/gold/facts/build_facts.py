import logging

import pandas as pd
from sqlalchemy import create_engine, text, inspect

logger = logging.getLogger(__name__)


def _assert_dimensions_exist(engine) -> None:
    inspector = inspect(engine)
    gold_tables = inspector.get_table_names(schema="gold")
    missing = [t for t in ("dim_date", "dim_suppliers") if t not in gold_tables]
    if missing:
        raise RuntimeError(
            f"Missing required gold dimension table(s): {missing}. "
            "Run build_dimensions.py before build_facts.py."
        )

def _build_fact_purchase_orders(engine) -> pd.DataFrame:
    query = text("""
        SELECT
            po.po_id,
            po.po_line_id,
            po.supplier_id,
            po.sku,
            po.po_date,
            po.promised_delivery_date,
            po.actual_delivery_date,
            po.po_quantity,
            po.unit_cost_at_po,
            po.incoterm,
            po.freight_mode,
            po.origin_country,
            po.destination_country,
            po.po_status,
            d.date_key AS po_date_key,
            s.supplier_tier
        FROM bronze.bronze_purchase_orders po
        LEFT JOIN gold.dim_date d
            ON po.po_date = d.full_date
        LEFT JOIN gold.dim_suppliers s
            ON po.supplier_id = s.supplier_id
            AND s.is_current = true
    """)
    df = pd.read_sql(query, engine)

    unmatched_date = df["po_date_key"].isna().sum()
    unmatched_supplier = df["supplier_tier"].isna().sum()
    if unmatched_date:
        logger.warning(
            "%d purchase order rows did not match a gold.dim_date row -- "
            "check dim_date's date range covers all po_date values.",
            unmatched_date,
        )
    if unmatched_supplier:
        logger.warning(
            "%d purchase order rows did not match a current gold.dim_suppliers "
            "row -- supplier_id may be missing from suppliers_scd2 or not "
            "marked is_current.",
            unmatched_supplier,
        )
    return df


def _build_fact_order_lines(engine) -> pd.DataFrame:
    query = text("""
        SELECT
            o.order_item_id,
            o.customer_id,
            o.sku,
            o.order_date,
            o.order_status,
            o.order_item_quantity,
            o.order_item_unit_price,
            o.order_item_discount_pct,
            o.order_item_total,
            d.date_key AS order_date_key
        FROM silver.orders o
        LEFT JOIN gold.dim_date d
            ON o.order_date::date = d.full_date
    """)
    df = pd.read_sql(query, engine)

    unmatched_date = df["order_date_key"].isna().sum()
    if unmatched_date:
        logger.warning(
            "%d order line rows did not match a gold.dim_date row -- "
            "check dim_date's date range covers all order_date values.",
            unmatched_date,
        )
    return df


def _build_fact_demand_forecast(engine) -> pd.DataFrame:
    query = text("""
        SELECT
            f.sku,
            f.forecast_week,
            f.predicted_next_week_qty,
            f.model_mae,
            f.fitted_at,
            d.date_key AS forecast_week_date_key
        FROM silver.demand_forecast f
        LEFT JOIN gold.dim_date d
            ON f.forecast_week::date = d.full_date
    """)
    df = pd.read_sql(query, engine)

    unmatched_date = df["forecast_week_date_key"].isna().sum()
    if unmatched_date:
        logger.warning(
            "%d demand forecast rows did not match a gold.dim_date row -- "
            "dim_date's 90-day forward pad may not be sufficient. "
            "Rebuild build_dimensions.py with a larger pad if this is large.",
            unmatched_date,
        )
    return df


def _write(engine, df: pd.DataFrame, table_name: str) -> None:
    df.to_sql(table_name, engine, schema="gold", if_exists="replace", index=False)
    logger.info("Wrote %d rows to gold.%s", len(df), table_name)


def build_facts(conn_str: str) -> dict:
    engine = create_engine(conn_str)
    _assert_dimensions_exist(engine)

    summary = {}

    fact_po = _build_fact_purchase_orders(engine)
    _write(engine, fact_po, "fact_purchase_orders")
    summary["fact_purchase_orders"] = len(fact_po)

    fact_orders = _build_fact_order_lines(engine)
    _write(engine, fact_orders, "fact_order_lines")
    summary["fact_order_lines"] = len(fact_orders)

    fact_forecast = _build_fact_demand_forecast(engine)
    _write(engine, fact_forecast, "fact_demand_forecast")
    summary["fact_demand_forecast"] = len(fact_forecast)

    logger.warning(
        "fact_inventory_snapshot and fact_late_delivery_risk were NOT built -- "
        "see module docstring for why (open upstream bugs / unconfirmed schema)."
    )
    summary["fact_inventory_snapshot"] = "SKIPPED -- upstream clean_inventory.py issue unresolved"
    summary["fact_late_delivery_risk"] = "SKIPPED -- source schema not confirmed"

    logger.info("build_facts summary: %s", summary)
    return summary


def run(conn_str: str, **context) -> dict:
    return build_facts(conn_str)


if __name__ == "__main__":
    import os
    logging.basicConfig(level=logging.INFO)
    conn_str = os.environ.get(
        "WAREHOUSE_CONN_STRING",
        "postgresql+psycopg2://warehouse_admin:CHANGEME@postgres_warehouse:5432/resilience_warehouse",
    )
    print(run(conn_str))