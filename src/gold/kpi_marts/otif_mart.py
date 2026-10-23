import logging

import pandas as pd
from sqlalchemy import create_engine, text, inspect

logger = logging.getLogger(__name__)

# PO lines in these statuses are considered "resolved" and eligible for an
# OTIF judgment. OPEN (not yet delivered) and CANCELED (never fulfilled)
# are excluded from the denominator entirely -- see module docstring.
RESOLVED_STATUSES = ("CLOSED", "PARTIALLY_RECEIVED")


def _assert_fact_table_exists(engine) -> None:
    inspector = inspect(engine)
    gold_tables = inspector.get_table_names(schema="gold")
    if "fact_purchase_orders" not in gold_tables:
        raise RuntimeError(
            "gold.fact_purchase_orders does not exist. Run build_facts.py "
            "before otif_mart.py."
        )


def _fetch_resolved_po_lines(engine) -> pd.DataFrame:
    query = text("""
        SELECT
            po_id,
            po_line_id,
            supplier_id,
            supplier_tier,
            po_date,
            promised_delivery_date,
            actual_delivery_date,
            po_status
        FROM gold.fact_purchase_orders
        WHERE po_status = ANY(:resolved_statuses)
    """)
    df = pd.read_sql(query, engine, params={"resolved_statuses": list(RESOLVED_STATUSES)})

    missing_actual_date = df["actual_delivery_date"].isna().sum()
    if missing_actual_date:
        logger.warning(
            "%d resolved PO lines (status in %s) have a NULL actual_delivery_date -- "
            "these cannot be scored for on-time and will be excluded.",
            missing_actual_date, RESOLVED_STATUSES,
        )
    return df[df["actual_delivery_date"].notna()].copy()


def _score_otif(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["promised_delivery_date"] = pd.to_datetime(df["promised_delivery_date"])
    df["actual_delivery_date"] = pd.to_datetime(df["actual_delivery_date"])
    df["po_date"] = pd.to_datetime(df["po_date"])

    df["is_on_time"] = df["actual_delivery_date"] <= df["promised_delivery_date"]
    # Proxy for "in full" -- see module docstring. PARTIALLY_RECEIVED is the
    # only signal available in the absence of a received_quantity column.
    df["is_in_full"] = df["po_status"] != "PARTIALLY_RECEIVED"
    df["is_otif"] = df["is_on_time"] & df["is_in_full"]

    df["year_month"] = df["po_date"].dt.to_period("M").dt.to_timestamp()
    return df


def _aggregate_otif(scored: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        scored.groupby(["supplier_id", "supplier_tier", "year_month"])
        .agg(
            total_resolved_po_lines=("po_line_id", "count"),
            on_time_count=("is_on_time", "sum"),
            in_full_count=("is_in_full", "sum"),
            otif_count=("is_otif", "sum"),
        )
        .reset_index()
    )

    grouped["on_time_pct"] = (grouped["on_time_count"] / grouped["total_resolved_po_lines"] * 100).round(2)
    grouped["in_full_pct"] = (grouped["in_full_count"] / grouped["total_resolved_po_lines"] * 100).round(2)
    grouped["otif_pct"] = (grouped["otif_count"] / grouped["total_resolved_po_lines"] * 100).round(2)

    return grouped


def _write(engine, df: pd.DataFrame) -> None:
    df["built_at"] = pd.Timestamp.now()
    df.to_sql("otif_mart", engine, schema="gold", if_exists="replace", index=False)
    logger.info("Wrote %d supplier-month OTIF rows to gold.otif_mart", len(df))


def build_otif_mart(conn_str: str) -> dict:
    engine = create_engine(conn_str)
    _assert_fact_table_exists(engine)

    raw = _fetch_resolved_po_lines(engine)
    if raw.empty:
        raise ValueError(
            "No resolved PO lines (status CLOSED or PARTIALLY_RECEIVED with a "
            "non-null actual_delivery_date) found in gold.fact_purchase_orders."
        )

    scored = _score_otif(raw)
    aggregated = _aggregate_otif(scored)
    _write(engine, aggregated)

    overall_otif_pct = round(scored["is_otif"].mean() * 100, 2)
    summary = {
        "total_resolved_po_lines_scored": len(scored),
        "supplier_month_rows_written": len(aggregated),
        "overall_otif_pct": overall_otif_pct,
    }
    logger.info("otif_mart summary: %s", summary)
    return summary


def run(conn_str: str, **context) -> dict:
    return build_otif_mart(conn_str)


if __name__ == "__main__":
    import os
    logging.basicConfig(level=logging.INFO)
    conn_str = os.environ.get(
        "WAREHOUSE_CONN_STRING",
        "postgresql+psycopg2://warehouse_admin:CHANGEME@postgres_warehouse:5432/resilience_radar",
    )
    print(run(conn_str))