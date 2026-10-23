import logging
import json
from datetime import timezone

import pandas as pd
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)

VALID_ORDER_STATUSES = {
    "COMPLETE", "PENDING", "CLOSED", "CANCELED", "PROCESSING",
    "PENDING_PAYMENT", "ON_HOLD", "SUSPECTED_FRAUD", "PAYMENT_REVIEW",
}  


def _fetch_bronze_orders(engine) -> pd.DataFrame:
    query = text("SELECT * FROM bronze.bronze_orders")
    return pd.read_sql(query, engine)


def _apply_quality_rules(df: pd.DataFrame) -> pd.DataFrame:

    df = df.copy()
    df["_rule_failures"] = [[] for _ in range(len(df))]

    def _flag(mask, rule_name):
        df.loc[mask, "_rule_failures"] = df.loc[mask, "_rule_failures"].apply(
            lambda failures: failures + [rule_name]
        )

    _flag(df["order_item_quantity"].isna() | (df["order_item_quantity"] <= 0),
          "invalid_quantity")
    _flag(df["order_item_unit_price"].isna() | (df["order_item_unit_price"] <= 0),
          "invalid_unit_price")
    _flag(df["order_item_discount_pct"].isna()
          | (df["order_item_discount_pct"] < 0)
          | (df["order_item_discount_pct"] > 100),
          "invalid_discount_pct")
    _flag(df["order_date"].isna(), "missing_order_date")
    _flag(pd.to_datetime(df["order_date"], errors="coerce") > pd.Timestamp.now(),
          "future_dated_order")
    _flag(~df["order_status"].isin(VALID_ORDER_STATUSES), "invalid_order_status")
    _flag(df["customer_id"].isna(), "missing_customer_id")
    _flag(df["sku"].isna(), "missing_sku")

    expected_total = (
        df["order_item_unit_price"] * df["order_item_quantity"]
        * (1 - df["order_item_discount_pct"] / 100)
    ).round(2)
    total_mismatch = (df["order_item_total"] - expected_total).abs() > 0.05
    _flag(total_mismatch.fillna(True), "total_amount_mismatch")

    df["_is_valid"] = df["_rule_failures"].apply(len) == 0
    return df


def _deduplicate(clean_df: pd.DataFrame) -> pd.DataFrame:

    before = len(clean_df)
    deduped = clean_df.drop_duplicates(subset=["order_item_id"], keep="first")
    dropped = before - len(deduped)
    if dropped:
        logger.warning("Dropped %d exact-duplicate order_item_id rows", dropped)
    return deduped


def _write_quarantine(engine, failed_df: pd.DataFrame) -> None:
    if failed_df.empty:
        logger.info("No rows quarantined this run.")
        return

    quarantine_records = pd.DataFrame({
        "order_item_id": failed_df["order_item_id"],
        "rule_failed": failed_df["_rule_failures"].apply(lambda rules: ", ".join(rules)),
        "quarantined_at": pd.Timestamp.now(tz=timezone.utc),
        "raw_payload": failed_df.drop(columns=["_rule_failures", "_is_valid"]).apply(
            lambda row: json.dumps(row.to_dict(), default=str), axis=1
        ),
    })

    quarantine_records.to_sql(
        "dq_quarantine",
        engine,
        schema="silver",
        if_exists="append",
        index=False,
    )
    logger.info("Quarantined %d rows to silver.dq_quarantine", len(quarantine_records))


def _write_clean(engine, clean_df: pd.DataFrame) -> None:
    output = clean_df.drop(columns=["_rule_failures", "_is_valid"]).copy()
    output["cleaned_at"] = pd.Timestamp.now(tz=timezone.utc)

    output.to_sql(
        "orders",
        engine,
        schema="silver",
        if_exists="replace",
        index=False,
    )
    logger.info("Wrote %d clean rows to silver.orders", len(output))


def clean_orders(conn_str: str) -> dict:
    engine = create_engine(conn_str)

    raw = _fetch_bronze_orders(engine)
    if raw.empty:
        raise ValueError(
            "No rows returned from bronze.orders -- check bronze_ingestion has run."
        )

    evaluated = _apply_quality_rules(raw)

    clean = evaluated[evaluated["_is_valid"]]
    failed = evaluated[~evaluated["_is_valid"]]

    clean_deduped = _deduplicate(clean)

    _write_clean(engine, clean_deduped)
    _write_quarantine(engine, failed)

    summary = {
        "total_rows": len(raw),
        "clean_rows_written": len(clean_deduped),
        "quarantined_rows": len(failed),
        "duplicate_rows_dropped": len(clean) - len(clean_deduped),
    }
    logger.info("clean_orders summary: %s", summary)
    return summary


def run(conn_str: str, **context) -> None:
    """Airflow-callable entrypoint, matching the run(conn_str, **context)
    pattern used across all silver-stage files in this project.
    """
    clean_orders(conn_str)


if __name__ == "__main__":
    import os
    logging.basicConfig(level=logging.INFO)
    conn_str = os.environ.get(
        "WAREHOUSE_CONN_STRING",
        "postgresql+psycopg2://warehouse_admin:CHANGEME@postgres_warehouse:5432/resilience_radar",
    )
    clean_orders(conn_str)