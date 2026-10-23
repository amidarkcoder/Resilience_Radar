import logging

import pandas as pd
from sqlalchemy import create_engine

from src.silver.cleaning.apply_scd2 import apply_scd2

logger = logging.getLogger(__name__)

BUSINESS_KEY = "supplier_id"

TRACKED_ATTRS = [
    "supplier_name",
    "supplier_country",
    "supplier_city",
    "supplier_tier",
    "certification_status",
]


def _fetch_bronze_suppliers(engine) -> pd.DataFrame:
    query = """
        SELECT
            supplier_id,
            supplier_name,
            supplier_country,
            supplier_city,
            supplier_tier,
            certification_status,
            onboarding_date,
            snapshot_date
        FROM bronze.bronze_suppliers
    """
    return pd.read_sql(query, engine)


def _dedupe_to_latest_snapshot(df: pd.DataFrame) -> pd.DataFrame:

    before = len(df)
    df = df.sort_values("snapshot_date").drop_duplicates(
        subset="supplier_id", keep="last"
    )
    dropped = before - len(df)
    if dropped:
        logger.info(
            "Deduped %d stale/duplicate supplier snapshot rows (kept latest per supplier_id).",
            dropped,
        )
    return df.drop(columns=["snapshot_date"])


def _apply_quality_rules(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["_rule_failures"] = [[] for _ in range(len(df))]

    def _flag(mask: pd.Series, rule_name: str) -> None:
        for idx in df.index[mask]:
            df.at[idx, "_rule_failures"].append(rule_name)

    _flag(
        df["supplier_id"].isna() | (df["supplier_id"].astype(str).str.strip() == ""),
        "missing_supplier_id",
    )
    _flag(
        df["supplier_name"].isna() | (df["supplier_name"].astype(str).str.strip() == ""),
        "missing_supplier_name",
    )
    _flag(df["supplier_country"].isna(), "missing_supplier_country")
    _flag(df["supplier_tier"].isna(), "missing_supplier_tier")
    _flag(df["certification_status"].isna(), "missing_certification_status")
    _flag(df["onboarding_date"].isna(), "missing_onboarding_date")
    _flag(
        pd.to_datetime(df["onboarding_date"], errors="coerce") > pd.Timestamp.now(),
        "future_onboarding_date",
    )

    df["_is_valid"] = df["_rule_failures"].apply(len) == 0
    return df


def _write_quarantine(engine, failed: pd.DataFrame) -> None:
    if failed.empty:
        logger.info("No rows quarantined this run.")
        return

    quarantine_rows = pd.DataFrame({
        "source_record_id": failed["supplier_id"],
        "rule_failed": failed["_rule_failures"].apply(lambda rules: ",".join(rules)),
        "raw_payload": failed.drop(columns=["_rule_failures", "_is_valid"]).apply(
            lambda row: row.to_json(), axis=1
        ),
    })
    quarantine_rows.to_sql(
        "dq_quarantine", engine, schema="silver", if_exists="append", index=False
    )
    logger.warning("Quarantined %d supplier rows.", len(failed))


def clean_suppliers(conn_str: str) -> dict:
    engine = create_engine(conn_str)

    raw = _fetch_bronze_suppliers(engine)
    if raw.empty:
        raise ValueError(
            "No rows returned from bronze.bronze_suppliers -- check bronze_ingestion has run."
        )

    raw = _dedupe_to_latest_snapshot(raw)

    evaluated = _apply_quality_rules(raw)

    clean = evaluated[evaluated["_is_valid"]].drop(columns=["_rule_failures", "_is_valid"])
    failed = evaluated[~evaluated["_is_valid"]]

    scd2_summary = apply_scd2(
        engine,
        clean,
        schema="silver",
        table="suppliers_scd2",
        business_key=BUSINESS_KEY,
        tracked_attrs=TRACKED_ATTRS,
    )

    _write_quarantine(engine, failed)

    summary = {
        "total_rows": len(raw),
        "quarantined_rows": len(failed),
        **scd2_summary,
    }
    logger.info("clean_suppliers summary: %s", summary)
    return summary


def run(conn_str: str, **context) -> dict:
    return clean_suppliers(conn_str)


if __name__ == "__main__":
    import os
    logging.basicConfig(level=logging.INFO)
    conn_str = os.environ.get(
        "WAREHOUSE_CONN_STRING",
        "postgresql+psycopg2://warehouse_admin:CHANGEME@postgres_warehouse:5432/resilience_radar",
    )
    print(run(conn_str))