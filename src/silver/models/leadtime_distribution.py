import logging

import numpy as np
import pandas as pd
from scipy import stats
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)

MIN_SAMPLE_SIZE = 8  # below this, fall back to simple moments instead of
                      # trusting a fitted lognormal shape/scale


def _fetch_completed_purchase_orders(engine) -> pd.DataFrame:
    query = text("""
        SELECT
            po.po_line_id,
            po.supplier_id,
            po.po_date,
            po.actual_delivery_date,
            s.supplier_tier
        FROM bronze.bronze_purchase_orders po
        LEFT JOIN bronze.bronze_suppliers s
            ON po.supplier_id = s.supplier_id
        WHERE po.actual_delivery_date IS NOT NULL
    """)
    return pd.read_sql(query, engine)


def _dedupe_exact_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """
    bronze_ingestion is append-only; re-triggers have repeatedly produced
    exact-duplicate rows in every bronze table touched this session
    (orders, suppliers, inventory_snapshots). Defensively dedupe on the
    line-item business key before fitting, same pattern as clean_orders.py.
    """
    before = len(df)
    df = df.drop_duplicates(subset=["po_line_id"], keep="last")
    dropped = before - len(df)
    if dropped:
        logger.warning("Dropped %d exact-duplicate po_line_id rows", dropped)
    return df


def _compute_lead_times(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["po_date"] = pd.to_datetime(df["po_date"], errors="coerce")
    df["actual_delivery_date"] = pd.to_datetime(df["actual_delivery_date"], errors="coerce")

    df["lead_time_days"] = (df["actual_delivery_date"] - df["po_date"]).dt.days

    # Guard against nonsensical rows: missing dates after coercion, or a
    # delivery date that is on/before the PO date (negative or zero lead
    # time is not physically meaningful for a supplier lead time).
    before = len(df)
    df = df[df["lead_time_days"].notna() & (df["lead_time_days"] > 0)]
    dropped = before - len(df)
    if dropped:
        logger.warning(
            "Dropped %d rows with missing or non-positive lead_time_days", dropped
        )
    return df


def _fit_supplier_distributions(df: pd.DataFrame) -> pd.DataFrame:
    records = []

    for supplier_id, group in df.groupby("supplier_id"):
        lead_times = group["lead_time_days"].to_numpy()
        sample_size = len(lead_times)
        supplier_tier = group["supplier_tier"].iloc[0] if not group["supplier_tier"].isna().all() else None

        if sample_size < MIN_SAMPLE_SIZE:
            # Not enough observations to trust a fitted distribution shape --
            # fall back to simple descriptive moments instead.
            records.append({
                "supplier_id": supplier_id,
                "supplier_tier": supplier_tier,
                "distribution_type": "insufficient_data_moments",
                "lognorm_shape": None,
                "lognorm_scale": None,
                "mean_lead_time_days": float(np.mean(lead_times)),
                "stddev_lead_time_days": float(np.std(lead_times, ddof=1)) if sample_size > 1 else 0.0,
                "sample_size": sample_size,
            })
            continue

        # floc=0 anchors the distribution at zero (lead time can't be negative)
        shape, loc, scale = stats.lognorm.fit(lead_times, floc=0)
        records.append({
            "supplier_id": supplier_id,
            "supplier_tier": supplier_tier,
            "distribution_type": "lognormal",
            "lognorm_shape": float(shape),
            "lognorm_scale": float(scale),
            "mean_lead_time_days": float(np.mean(lead_times)),
            "stddev_lead_time_days": float(np.std(lead_times, ddof=1)),
            "sample_size": sample_size,
        })

    return pd.DataFrame.from_records(records)


def _write_params(engine, params_df: pd.DataFrame) -> None:
    params_df["fitted_at"] = pd.Timestamp.now()
    params_df.to_sql(
        "supplier_leadtime_params",
        engine,
        schema="silver",
        if_exists="replace",
        index=False,
    )
    logger.info("Wrote lead-time params for %d suppliers to silver.supplier_leadtime_params", len(params_df))


def fit_leadtime_distributions(conn_str: str) -> dict:
    engine = create_engine(conn_str)

    raw = _fetch_completed_purchase_orders(engine)
    if raw.empty:
        raise ValueError(
            "No completed purchase orders found (actual_delivery_date IS NOT NULL) "
            "-- check bronze_ingestion has run and POs have delivery dates."
        )

    raw = _dedupe_exact_duplicates(raw)
    with_lead_times = _compute_lead_times(raw)

    if with_lead_times.empty:
        raise ValueError(
            "No valid lead-time observations remained after cleaning -- "
            "check po_date/actual_delivery_date values."
        )

    params = _fit_supplier_distributions(with_lead_times)
    _write_params(engine, params)

    summary = {
        "total_po_lines": len(raw),
        "valid_lead_time_observations": len(with_lead_times),
        "suppliers_fitted": len(params),
        "suppliers_fallback_moments": int((params["distribution_type"] == "insufficient_data_moments").sum()),
    }
    logger.info("leadtime_distribution summary: %s", summary)
    return summary


def run(conn_str: str, **context) -> dict:
    return fit_leadtime_distributions(conn_str)


if __name__ == "__main__":
    import os
    logging.basicConfig(level=logging.INFO)
    conn_str = os.environ.get(
        "WAREHOUSE_CONN_STRING",
        "postgresql+psycopg2://warehouse_admin:CHANGEME@postgres_warehouse:5432/resilience_radar",
    )
    print(run(conn_str))