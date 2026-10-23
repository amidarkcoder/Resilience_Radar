"""
clean_inventory.py -- Silver: clean bronze.bronze_inventory_snapshots.

Grain = (sku, location_id, snapshot_date). Bronze is append-only and gets
re-triggered multiple times across sessions, so dedupe across _batch_id IN SQL
(keep latest batch per grain) so pandas never sees un-deduped rows, and so
re-running bronze never silently re-quarantines everything.
"""
import logging

import pandas as pd
from sqlalchemy import create_engine

logger = logging.getLogger(__name__)

SOURCE_TABLE = "bronze.bronze_inventory_snapshots"
TARGET_SCHEMA = "silver"
TARGET_TABLE = "inventory_snapshots"
QUARANTINE_TABLE = "dq_quarantine"   # CONFIRMED real table name this session

GRAIN = ["sku", "location_id", "snapshot_date"]

# CONFIRMED via `SELECT column_name FROM information_schema.columns
# WHERE table_schema='silver' AND table_name='dq_quarantine';`
# this session: source_record_id, rule_failed, quarantined_at, raw_payload
QUARANTINE_COLUMNS = ["source_record_id", "rule_failed", "quarantined_at", "raw_payload"]

FETCH_QUERY = f"""
    SELECT DISTINCT ON (sku, location_id, snapshot_date)
           sku, location_id, location_type, snapshot_date,
           on_hand_qty, on_order_qty, backorder_qty, safety_stock_target_qty,
           _batch_id, _source_file
    FROM {SOURCE_TABLE}
    ORDER BY sku, location_id, snapshot_date, _batch_id DESC
"""


def _fetch_bronze_inventory(engine) -> pd.DataFrame:
    df = pd.read_sql(FETCH_QUERY, engine)
    logger.info("Fetched %d deduped rows from %s", len(df), SOURCE_TABLE)
    return df


def _apply_rules(df: pd.DataFrame) -> pd.DataFrame:
    """Flag rows that fail DQ rules. Adds _quarantine_reason (NA if clean)."""
    df = df.copy()
    df["_quarantine_reason"] = pd.NA
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"], errors="coerce")

    def _flag(mask, reason):
        df.loc[mask & df["_quarantine_reason"].isna(), "_quarantine_reason"] = reason

    _flag(df["sku"].isna() | (df["sku"].astype(str).str.strip() == ""), "missing_sku")
    _flag(df["location_id"].isna(), "missing_location_id")
    _flag(df["snapshot_date"].isna(), "missing_snapshot_date")
    _flag(df["snapshot_date"] > pd.Timestamp.now(), "future_dated")
    _flag(df["on_hand_qty"].isna() | (df["on_hand_qty"] < 0), "invalid_on_hand")
    _flag(df["on_order_qty"].isna() | (df["on_order_qty"] < 0), "invalid_on_order")
    _flag(df["backorder_qty"].isna() | (df["backorder_qty"] < 0), "invalid_backorder")
    _flag(df["safety_stock_target_qty"].notna() & (df["safety_stock_target_qty"] < 0),
          "invalid_safety_stock_target")
    _flag(df.duplicated(subset=GRAIN, keep=False), "duplicate_grain")
    return df


def _build_quarantine_rows(bad: pd.DataFrame) -> pd.DataFrame:
    """
    Build rows matching silver.dq_quarantine's real schema:
    source_record_id, rule_failed, quarantined_at, raw_payload.

    IMPORTANT: reset_index first so every array we build below is positionally
    aligned to `bad`, regardless of what the index looked like after filtering
    upstream. This is almost certainly what caused the previous
    "All arrays must be of the same length" ValueError -- a stale/non-contiguous
    index or a column accidentally pulled from a different-length source.
    """
    bad = bad.reset_index(drop=True)

    source_record_id = (
        bad["sku"].astype(str)
        + "|" + bad["location_id"].astype(str)
        + "|" + bad["snapshot_date"].astype(str)
    )
    rule_failed = bad["_quarantine_reason"].astype(str)
    quarantined_at = pd.Timestamp.now()  # scalar -- pandas broadcasts this safely
    raw_payload = bad.drop(columns=["_quarantine_reason"]).to_dict(orient="records")

    quarantine_df = pd.DataFrame({
        "source_record_id": source_record_id,
        "rule_failed": rule_failed,
        "quarantined_at": quarantined_at,
        "raw_payload": raw_payload,
    })

    assert len(quarantine_df) == len(bad), (
        f"quarantine row count {len(quarantine_df)} != bad row count {len(bad)}"
    )
    return quarantine_df


def _write_clean(engine, df: pd.DataFrame) -> None:
    df = df.drop(columns=["_quarantine_reason"], errors="ignore")
    df.to_sql(TARGET_TABLE, engine, schema=TARGET_SCHEMA, if_exists="replace",
              index=False, chunksize=5000, method="multi")


def _write_quarantine(engine, quarantine_df: pd.DataFrame) -> None:
    import json

    df = quarantine_df.copy()
    # raw_payload is a dict column; if dq_quarantine.raw_payload is jsonb/json,
    # serialize explicitly rather than relying on to_sql's generic adapter.
    # ASSUMPTION: raw_payload column type is json/jsonb. If it's text, this is
    # still safe (valid JSON string). If it's something else, flag and adjust.
    df["raw_payload"] = df["raw_payload"].apply(json.dumps)

    df.to_sql(QUARANTINE_TABLE, engine, schema=TARGET_SCHEMA, if_exists="append",
              index=False, chunksize=5000, method="multi")


def clean_inventory(conn_str: str) -> dict:
    engine = create_engine(conn_str)
    raw = _fetch_bronze_inventory(engine)
    if raw.empty:
        raise ValueError(f"{SOURCE_TABLE} returned 0 rows")

    flagged = _apply_rules(raw)
    bad_mask = flagged["_quarantine_reason"].notna()
    bad = flagged[bad_mask]
    clean = flagged[~bad_mask]

    _write_clean(engine, clean)
    logger.info("Wrote %d clean rows to %s.%s", len(clean), TARGET_SCHEMA, TARGET_TABLE)

    if not bad.empty:
        quarantine_rows = _build_quarantine_rows(bad)
        _write_quarantine(engine, quarantine_rows)
        logger.info("Quarantined %d inventory rows to %s.%s",
                    len(quarantine_rows), TARGET_SCHEMA, QUARANTINE_TABLE)
    else:
        logger.info("No rows quarantined this run.")

    summary = {
        "total_rows": len(raw),
        "clean_rows_written": len(clean),
        "quarantined_rows": len(bad),
        "quarantine_breakdown": bad["_quarantine_reason"].value_counts().to_dict() if not bad.empty else {},
    }
    logger.info("clean_inventory summary: %s", summary)
    return summary


def run(conn_str: str, **context) -> dict:
    return clean_inventory(conn_str)


if __name__ == "__main__":
    import os
    logging.basicConfig(level=logging.INFO)
    conn_str = os.environ.get(
        "WAREHOUSE_CONN_STRING",
        "postgresql+psycopg2://warehouse_admin:CHANGEME@postgres_warehouse:5432/resilience_radar",
    )
    print(run(conn_str))