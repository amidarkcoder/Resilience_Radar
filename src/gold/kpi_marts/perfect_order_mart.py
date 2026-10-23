import logging

import pandas as pd
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)

# Statuses treated as "not completed" -- orders that never successfully
# fulfilled, so they can't be judged on-time/in-full at all.
# ASSUMPTION: based on the DataCo reference dataset's status vocabulary,
# NOT confirmed against this project's real order_status values.
INCOMPLETE_STATUSES = ("CANCELED", "SUSPECTED_FRAUD")


def _fetch_order_grain_data(engine) -> pd.DataFrame:

    query = text("""
        SELECT
            order_id,
            customer_id,
            order_date,
            order_status,
            late_delivery_risk,
            COUNT(DISTINCT order_status) AS distinct_status_count,
            COUNT(DISTINCT late_delivery_risk) AS distinct_risk_count
        FROM silver.orders
        GROUP BY order_id, customer_id, order_date, order_status, late_delivery_risk
    """)
    df = pd.read_sql(query, engine)

    inconsistent = df[(df["distinct_status_count"] > 1) | (df["distinct_risk_count"] > 1)]
    if not inconsistent.empty:
        logger.warning(
            "%d order_id groups have inconsistent order_status/late_delivery_risk "
            "across their line items -- the order-grain-attribute assumption may "
            "be wrong. Inspect silver.orders for these order_ids: %s",
            len(inconsistent), inconsistent["order_id"].unique()[:10].tolist(),
        )

    return df.drop(columns=["distinct_status_count", "distinct_risk_count"]).drop_duplicates(subset=["order_id"])


def _score_perfect_order(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["order_date"] = pd.to_datetime(df["order_date"])

    df["is_on_time"] = df["late_delivery_risk"] == 0
    df["is_completed"] = ~df["order_status"].isin(INCOMPLETE_STATUSES)
    df["is_perfect_order"] = df["is_on_time"] & df["is_completed"]

    df["year_month"] = df["order_date"].dt.to_period("M").dt.to_timestamp()
    return df


def _aggregate_perfect_order(scored: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        scored.groupby("year_month")
        .agg(
            total_orders=("order_id", "count"),
            completed_orders=("is_completed", "sum"),
            on_time_orders=("is_on_time", "sum"),
            perfect_orders=("is_perfect_order", "sum"),
        )
        .reset_index()
    )

    grouped["completed_pct"] = (grouped["completed_orders"] / grouped["total_orders"] * 100).round(2)
    grouped["on_time_pct"] = (grouped["on_time_orders"] / grouped["total_orders"] * 100).round(2)
    grouped["perfect_order_pct"] = (grouped["perfect_orders"] / grouped["total_orders"] * 100).round(2)

    return grouped.sort_values("year_month")


def _write(engine, df: pd.DataFrame) -> None:
    df["built_at"] = pd.Timestamp.now()
    df.to_sql("perfect_order_mart", engine, schema="gold", if_exists="replace", index=False)
    logger.info("Wrote %d monthly perfect-order rows to gold.perfect_order_mart", len(df))


def build_perfect_order_mart(conn_str: str) -> dict:
    engine = create_engine(conn_str)

    raw = _fetch_order_grain_data(engine)
    if raw.empty:
        raise ValueError("No rows returned from silver.orders -- check clean_orders.py has run.")

    scored = _score_perfect_order(raw)
    aggregated = _aggregate_perfect_order(scored)
    _write(engine, aggregated)

    overall_perfect_pct = round(scored["is_perfect_order"].mean() * 100, 2)
    summary = {
        "total_orders_scored": len(scored),
        "monthly_rows_written": len(aggregated),
        "overall_perfect_order_pct": overall_perfect_pct,
    }
    logger.info("perfect_order_mart summary: %s", summary)
    return summary


def run(conn_str: str, **context) -> dict:
    return build_perfect_order_mart(conn_str)


if __name__ == "__main__":
    import os
    logging.basicConfig(level=logging.INFO)
    conn_str = os.environ.get(
        "WAREHOUSE_CONN_STRING",
        "postgresql+psycopg2://warehouse_admin:CHANGEME@postgres_warehouse:5432/resilience_radar",
    )
    print(run(conn_str))