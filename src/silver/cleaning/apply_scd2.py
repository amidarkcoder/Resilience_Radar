import hashlib
import logging

import pandas as pd
from sqlalchemy import bindparam, text

logger = logging.getLogger(__name__)


def _compute_record_hash(row: pd.Series, tracked_attrs: list[str]) -> str:
    payload = "|".join(str(row[attr]) for attr in tracked_attrs)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def fetch_current_rows(engine, schema: str, table: str, business_key: str) -> pd.DataFrame:
    query = text(f"SELECT * FROM {schema}.bronze_{table} WHERE is_current = TRUE")
    try:
        return pd.read_sql(query, engine)
    except Exception:
        logger.warning(
            "%s.%s not found or empty -- treating as first run for this dimension.",
            schema, table,
        )
        return pd.DataFrame(columns=[business_key, "record_hash"])


def build_changeset(clean_df: pd.DataFrame, current_df: pd.DataFrame,
                     business_key: str, tracked_attrs: list[str]) -> dict:
    clean_df = clean_df.copy()
    clean_df["record_hash"] = clean_df.apply(
        lambda row: _compute_record_hash(row, tracked_attrs), axis=1
    )

    current_hashes = (
        current_df.set_index(business_key)["record_hash"]
        if "record_hash" in current_df.columns and not current_df.empty
        else pd.Series(dtype=str)
    )

    is_new = ~clean_df[business_key].isin(current_hashes.index)
    new_rows = clean_df[is_new]

    existing = clean_df[~is_new].copy()
    existing["_current_hash"] = existing[business_key].map(current_hashes)
    is_changed = existing["record_hash"] != existing["_current_hash"]

    changed_rows = existing[is_changed].drop(columns=["_current_hash"])
    unchanged_rows = existing[~is_changed].drop(columns=["_current_hash"])

    return {"new": new_rows, "changed": changed_rows, "unchanged": unchanged_rows}


def write_changeset(engine, changeset: dict, schema: str, table: str,
                     business_key: str, tracked_attrs: list[str]) -> None:
    now = pd.Timestamp.now(tz="UTC")

    to_insert = pd.concat([changeset["new"], changeset["changed"]], ignore_index=True)
    if to_insert.empty:
        logger.info("No new or changed rows for %s.%s -- table unchanged.", schema, table)
        return

    to_insert["valid_from"] = now
    to_insert["valid_to"] = pd.NaT
    to_insert["is_current"] = True

    if not changeset["changed"].empty:
        changed_keys = changeset["changed"][business_key].tolist()
        stmt = text(f"""
            UPDATE {schema}.{table}
            SET valid_to = :now, is_current = FALSE
            WHERE {business_key} IN :keys AND is_current = TRUE
        """).bindparams(bindparam("keys", expanding=True))

        with engine.begin() as conn:
            conn.execute(stmt, {"now": now, "keys": changed_keys})

    insert_cols = tracked_attrs + [business_key, "record_hash", "valid_from", "valid_to", "is_current"]
    to_insert[insert_cols].to_sql(
        table, engine, schema=schema, if_exists="append", index=False,
    )

    logger.info(
        "%s.%s updated: %d new rows, %d changed (new version inserted).",
        schema, table, len(changeset["new"]), len(changeset["changed"]),
    )


def apply_scd2(engine, clean_df: pd.DataFrame, schema: str, table: str,
                business_key: str, tracked_attrs: list[str]) -> dict:

    current = fetch_current_rows(engine, schema, table, business_key)
    changeset = build_changeset(clean_df, current, business_key, tracked_attrs)
    write_changeset(engine, changeset, schema, table, business_key, tracked_attrs)

    return {
        "new": len(changeset["new"]),
        "changed": len(changeset["changed"]),
        "unchanged": len(changeset["unchanged"]),
    }