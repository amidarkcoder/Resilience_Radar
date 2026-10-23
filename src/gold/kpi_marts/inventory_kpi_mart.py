import logging
import os

import pandas as pd
from sqlalchemy import create_engine, inspect, text

logger = logging.getLogger(__name__)

# Correct source is silver. Override ONLY for a temporary smoke test while
# clean_inventory.py is still broken, e.g.
#   INVENTORY_SOURCE_TABLE=bronze.bronze_inventory_snapshots
SOURCE_TABLE = os.environ.get("INVENTORY_SOURCE_TABLE", "silver.inventory_snapshots")
TARGET_SCHEMA = "gold"
TARGET_TABLE = "inventory_kpi_mart"


def _assert_source_exists(engine) -> None:
    schema, table = SOURCE_TABLE.split(".", 1)
    if table not in inspect(engine).get_table_names(schema=schema):
        raise RuntimeError(
            f"{SOURCE_TABLE} does not exist. Run clean_inventory.py "
            "(silver DAG) before inventory_kpi_mart.py."
        )
    if schema != "silver":
        logger.warning(
            "inventory_kpi_mart is reading %s -- NOT the silver layer. "
            "This bypasses cleaning and should only be a temporary smoke test.",
            SOURCE_TABLE,
        )


def _source_row_count(engine) -> int:
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT COUNT(*) FROM {SOURCE_TABLE}")).scalar()


def _aggregate_in_sql(engine) -> pd.DataFrame:
    """All heavy lifting in Postgres; pandas only receives sku x month rows."""
    query = f"""
    WITH deduped AS (
        SELECT DISTINCT ON (sku, location_id, snapshot_date)
               sku,
               location_id,
               snapshot_date::date                    AS snapshot_date,
               COALESCE(on_hand_qty, 0)::numeric      AS on_hand_qty,
               COALESCE(on_order_qty, 0)::numeric     AS on_order_qty,
               COALESCE(backorder_qty, 0)::numeric    AS backorder_qty
        FROM {SOURCE_TABLE}
        WHERE sku IS NOT NULL AND snapshot_date IS NOT NULL
        ORDER BY sku, location_id, snapshot_date
    ),
    scored AS (
        SELECT sku,
               location_id,
               date_trunc('month', snapshot_date)::date AS year_month,
               on_hand_qty,
               on_order_qty,
               backorder_qty,
               on_hand_qty + on_order_qty               AS total_position,
               (on_hand_qty = 0)                        AS is_stockout,
               (backorder_qty > 0)                      AS has_backorder
        FROM deduped
    )
    SELECT sku,
           year_month,
           COUNT(*)                                          AS snapshot_count,
           COUNT(DISTINCT location_id)                      AS warehouse_count,
           COUNT(*) FILTER (WHERE is_stockout)               AS stockout_snapshot_count,
           COUNT(*) FILTER (WHERE has_backorder)             AS backorder_snapshot_count,
           ROUND(AVG(on_hand_qty), 1)                        AS avg_on_hand_qty,
           ROUND(AVG(on_order_qty), 1)                       AS avg_on_order_qty,
           ROUND(AVG(backorder_qty), 1)                      AS avg_backorder_qty,
           SUM(backorder_qty)                                AS total_backorder_units,
           ROUND(AVG(total_position), 1)                     AS avg_total_position,
           ROUND(100.0 * COUNT(*) FILTER (WHERE is_stockout)   / COUNT(*), 2) AS stockout_rate_pct,
           ROUND(100.0 * COUNT(*) FILTER (WHERE has_backorder) / COUNT(*), 2) AS backorder_incidence_pct
    FROM scored
    GROUP BY sku, year_month
    ORDER BY sku, year_month
    """
    return pd.read_sql(query, engine)


def _write(engine, df: pd.DataFrame) -> None:
    df = df.copy()
    df["built_at"] = pd.Timestamp.now()
    df.to_sql(
        TARGET_TABLE, engine, schema=TARGET_SCHEMA,
        if_exists="replace", index=False, chunksize=5000, method="multi",
    )
    logger.info("Wrote %d sku-month rows to %s.%s", len(df), TARGET_SCHEMA, TARGET_TABLE)


def build_inventory_kpi_mart(conn_str: str) -> dict:
    engine = create_engine(conn_str)
    _assert_source_exists(engine)

    n_source = _source_row_count(engine)
    if n_source == 0:
        raise ValueError(
            f"{SOURCE_TABLE} has 0 rows -- clean_inventory.py is still writing "
            "0 clean rows. Fix _flag_duplicate_grain() subset "
            "(add warehouse_id) and re-run the silver DAG."
        )
    logger.info("Aggregating %d source rows from %s in SQL", n_source, SOURCE_TABLE)

    aggregated = _aggregate_in_sql(engine)
    if aggregated.empty:
        raise ValueError("Aggregation returned 0 rows -- check sku/snapshot_date nulls.")

    _write(engine, aggregated)

    total_snaps = int(aggregated["snapshot_count"].sum())
    total_stockouts = int(aggregated["stockout_snapshot_count"].sum())
    summary = {
        "source_table": SOURCE_TABLE,
        "source_rows": n_source,
        "deduped_snapshots_scored": total_snaps,
        "sku_month_rows_written": len(aggregated),
        "overall_stockout_rate_pct": round(100 * total_stockouts / total_snaps, 2),
    }
    logger.info("inventory_kpi_mart summary: %s", summary)
    return summary


def run(conn_str: str, **context) -> dict:
    return build_inventory_kpi_mart(conn_str)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    conn_str = os.environ.get(
        "WAREHOUSE_CONN_STRING",
        "postgresql+psycopg2://warehouse_admin:CHANGEME@postgres_warehouse:5432/resilience_radar",
    )
    print(run(conn_str))