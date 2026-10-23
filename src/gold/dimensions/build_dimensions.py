
import logging

import pandas as pd
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)


def _build_dim_date(engine) -> pd.DataFrame:
    query = text("""
        SELECT MIN(d) AS min_date, MAX(d) AS max_date FROM (
            SELECT order_date AS d FROM silver.orders
            UNION ALL
            SELECT po_date AS d FROM bronze.bronze_purchase_orders
            UNION ALL
            SELECT promised_delivery_date AS d FROM bronze.bronze_purchase_orders
            UNION ALL
            SELECT actual_delivery_date AS d FROM bronze.bronze_purchase_orders
                WHERE actual_delivery_date IS NOT NULL
        ) all_dates
    """)
    bounds = pd.read_sql(query, engine)
    min_date = pd.to_datetime(bounds["min_date"].iloc[0])
    # pad 90 days forward so forecast_week values from demand_forecast.py
    # (which project 1 week past the latest known week) always have a
    # matching dim_date row to join against
    max_date = pd.to_datetime(bounds["max_date"].iloc[0]) + pd.Timedelta(days=90)

    dates = pd.date_range(min_date, max_date, freq="D")
    dim = pd.DataFrame({"full_date": dates})
    dim["date_key"] = dim["full_date"].dt.strftime("%Y%m%d").astype(int)
    dim["year"] = dim["full_date"].dt.year
    dim["quarter"] = dim["full_date"].dt.quarter
    dim["month"] = dim["full_date"].dt.month
    dim["month_name"] = dim["full_date"].dt.month_name()
    dim["week_of_year"] = dim["full_date"].dt.isocalendar().week.astype(int)
    dim["day_of_week"] = dim["full_date"].dt.dayofweek
    dim["day_name"] = dim["full_date"].dt.day_name()
    dim["is_weekend"] = dim["day_of_week"].isin([5, 6])

    cols = [
        "date_key", "full_date", "year", "quarter", "month", "month_name",
        "week_of_year", "day_of_week", "day_name", "is_weekend",
    ]
    return dim[cols]


def _build_dim_suppliers(engine) -> pd.DataFrame:
    query = text("""
        SELECT
            supplier_id,
            supplier_name,
            supplier_country,
            supplier_city,
            supplier_tier,
            certification_status,
            valid_from,
            valid_to,
            is_current
        FROM silver.suppliers_scd2
    """)
    return pd.read_sql(query, engine)


def _write(engine, df: pd.DataFrame, table_name: str) -> None:
    df.to_sql(table_name, engine, schema="gold", if_exists="replace", index=False)
    logger.info("Wrote %d rows to gold.%s", len(df), table_name)


def build_dimensions(conn_str: str) -> dict:
    engine = create_engine(conn_str)
    summary = {}

    dim_date = _build_dim_date(engine)
    _write(engine, dim_date, "dim_date")
    summary["dim_date"] = len(dim_date)

    dim_suppliers = _build_dim_suppliers(engine)
    _write(engine, dim_suppliers, "dim_suppliers")
    summary["dim_suppliers"] = len(dim_suppliers)

    logger.warning(
        "dim_products, dim_customers, dim_warehouse were NOT built this run -- "
        "no confirmed source schema exists for products/customers, and "
        "warehouse_id existence on inventory_snapshots is still unconfirmed."
    )
    summary["dim_products"] = "SKIPPED -- schema not confirmed"
    summary["dim_customers"] = "SKIPPED -- schema not confirmed"
    summary["dim_warehouse"] = "SKIPPED -- warehouse_id existence unconfirmed"

    logger.info("build_dimensions summary: %s", summary)
    return summary


def run(conn_str: str, **context) -> dict:
    return build_dimensions(conn_str)


if __name__ == "__main__":
    import os
    logging.basicConfig(level=logging.INFO)
    conn_str = os.environ.get(
        "WAREHOUSE_CONN_STRING",
        "postgresql+psycopg2://warehouse_admin:CHANGEME@postgres_warehouse:5432/resilience_radar",
    )
    print(run(conn_str))