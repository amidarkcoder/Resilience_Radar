import logging

import numpy as np
import pandas as pd
from scipy import stats
from sqlalchemy import create_engine, text, inspect

logger = logging.getLogger(__name__)

N_SIMULATIONS = 5000
DISRUPTION_PROBABILITY = 0.08
DISRUPTION_SEVERITY_MULTIPLIER = 3.0
SERVICE_PERCENTILE = 95
RANDOM_SEED = 42


def _assert_sources_exist(engine) -> None:
    inspector = inspect(engine)
    silver_tables = inspector.get_table_names(schema="silver")
    if "supplier_leadtime_params" not in silver_tables:
        raise RuntimeError(
            "silver.supplier_leadtime_params does not exist. Run "
            "leadtime_distribution.py (via silver_processing DAG) first."
        )


def _derive_top2_suppliers_per_sku(engine) -> pd.DataFrame:
    query = text("""
        SELECT sku, supplier_id, COUNT(*) AS line_count
        FROM bronze.bronze_purchase_orders
        GROUP BY sku, supplier_id
    """)
    counts = pd.read_sql(query, engine)
    if counts.empty:
        return counts

    counts = counts.sort_values(
        ["sku", "line_count", "supplier_id"], ascending=[True, False, True]
    )
    counts["rank"] = counts.groupby("sku").cumcount() + 1
    top2 = counts[counts["rank"] <= 2].copy()

    pivoted = top2.pivot(index="sku", columns="rank", values="supplier_id").reset_index()
    pivoted.columns = ["sku", "primary_supplier_id", "secondary_supplier_id"]
    pivoted["n_distinct_suppliers_observed"] = (
        counts.groupby("sku")["supplier_id"].nunique().reindex(pivoted["sku"]).values
    )
    return pivoted


def _fetch_leadtime_params(engine) -> pd.DataFrame:
    query = text("""
        SELECT supplier_id, mean_lead_time_days, stddev_lead_time_days,
               distribution_type, lognorm_shape, lognorm_scale
        FROM silver.supplier_leadtime_params
    """)
    return pd.read_sql(query, engine).set_index("supplier_id")


def _sample_lead_times(params_row: pd.Series, n: int, rng: np.random.Generator) -> np.ndarray:
    """
    Draw n lead-time samples for a supplier. Uses the fitted lognormal if
    available; falls back to a normal distribution (truncated at 0) using
    simple moments for suppliers with insufficient history to fit a
    lognormal shape -- same fallback tier leadtime_distribution.py itself
    uses, now mirrored here for sampling instead of fitting.
    """
    if params_row["distribution_type"] == "lognormal":
        draws = stats.lognorm.rvs(
            s=params_row["lognorm_shape"],
            loc=0,
            scale=params_row["lognorm_scale"],
            size=n,
            random_state=rng,
        )
    else:
        draws = rng.normal(
            loc=params_row["mean_lead_time_days"],
            scale=max(params_row["stddev_lead_time_days"], 0.1),
            size=n,
        )
        draws = np.clip(draws, a_min=0.1, a_max=None)
    return draws


def _simulate_single_source(params_row: pd.Series, n: int, rng: np.random.Generator) -> np.ndarray:
    base_draws = _sample_lead_times(params_row, n, rng)
    disrupted = rng.random(n) < DISRUPTION_PROBABILITY
    draws = np.where(disrupted, base_draws * DISRUPTION_SEVERITY_MULTIPLIER, base_draws)
    return draws


def _simulate_dual_source(
    primary_params: pd.Series, secondary_params: pd.Series, n: int, rng: np.random.Generator
) -> np.ndarray:
    primary_base = _sample_lead_times(primary_params, n, rng)
    secondary_base = _sample_lead_times(secondary_params, n, rng)

    # Independent disruption draws -- see module docstring's critical
    # limitation regarding correlated real-world disruptions.
    primary_disrupted = rng.random(n) < DISRUPTION_PROBABILITY
    secondary_disrupted = rng.random(n) < DISRUPTION_PROBABILITY

    primary_effective = np.where(
        primary_disrupted, primary_base * DISRUPTION_SEVERITY_MULTIPLIER, primary_base
    )
    secondary_effective = np.where(
        secondary_disrupted, secondary_base * DISRUPTION_SEVERITY_MULTIPLIER, secondary_base
    )

    # If primary is fine, use it. If primary disrupted but secondary is
    # fine, reroute to secondary (no switchover cost modeled -- see
    # docstring). If both disrupted simultaneously, take the worse (max)
    # of the two as a conservative estimate of the realized delay.
    result = np.where(
        ~primary_disrupted,
        primary_effective,
        np.where(~secondary_disrupted, secondary_effective, np.maximum(primary_effective, secondary_effective)),
    )
    return result


def _run_simulation_for_all_skus(
    sku_suppliers: pd.DataFrame, leadtime_params: pd.DataFrame
) -> pd.DataFrame:
    rng = np.random.default_rng(RANDOM_SEED)
    records = []
    skipped_no_params = 0

    for _, row in sku_suppliers.iterrows():
        sku = row["sku"]
        primary_id = row["primary_supplier_id"]
        secondary_id = row["secondary_supplier_id"]

        if primary_id not in leadtime_params.index:
            skipped_no_params += 1
            continue
        primary_params = leadtime_params.loc[primary_id]

        single_draws = _simulate_single_source(primary_params, N_SIMULATIONS, rng)

        record = {
            "sku": sku,
            "primary_supplier_id": primary_id,
            "secondary_supplier_id": secondary_id,
            "n_distinct_suppliers_observed": row["n_distinct_suppliers_observed"],
            "mean_leadtime_single_days": round(float(np.mean(single_draws)), 2),
            "p95_leadtime_single_days": round(float(np.percentile(single_draws, SERVICE_PERCENTILE)), 2),
        }

        has_secondary = pd.notna(secondary_id) and secondary_id in leadtime_params.index
        if has_secondary:
            secondary_params = leadtime_params.loc[secondary_id]
            dual_draws = _simulate_dual_source(primary_params, secondary_params, N_SIMULATIONS, rng)

            p95_single = record["p95_leadtime_single_days"]
            p95_dual = round(float(np.percentile(dual_draws, SERVICE_PERCENTILE)), 2)

            record.update({
                "mean_leadtime_dual_days": round(float(np.mean(dual_draws)), 2),
                "p95_leadtime_dual_days": p95_dual,
                "p95_risk_reduction_pct": round((p95_single - p95_dual) / p95_single * 100, 2)
                    if p95_single > 0 else None,
            })
        else:
            record.update({
                "mean_leadtime_dual_days": None,
                "p95_leadtime_dual_days": None,
                "p95_risk_reduction_pct": None,
            })

        records.append(record)

    if skipped_no_params:
        logger.warning(
            "%d SKUs skipped entirely -- their primary supplier has no row "
            "in silver.supplier_leadtime_params.",
            skipped_no_params,
        )

    return pd.DataFrame.from_records(records)


def _write(engine, df: pd.DataFrame) -> None:
    df["disruption_probability_assumed"] = DISRUPTION_PROBABILITY
    df["disruption_severity_multiplier_assumed"] = DISRUPTION_SEVERITY_MULTIPLIER
    df["n_simulations"] = N_SIMULATIONS
    df["built_at"] = pd.Timestamp.now()
    df.to_sql("dual_sourcing_mc", engine, schema="gold", if_exists="replace", index=False)
    logger.info("Wrote %d SKU dual-sourcing simulation rows to gold.dual_sourcing_mc", len(df))


def build_dual_sourcing_mc(conn_str: str) -> dict:
    engine = create_engine(conn_str)
    _assert_sources_exist(engine)

    sku_suppliers = _derive_top2_suppliers_per_sku(engine)
    if sku_suppliers.empty:
        raise ValueError(
            "No sku->supplier mapping could be derived from "
            "bronze.bronze_purchase_orders -- check it has data."
        )

    leadtime_params = _fetch_leadtime_params(engine)
    if leadtime_params.empty:
        raise ValueError("silver.supplier_leadtime_params is empty -- run leadtime_distribution.py first.")

    result = _run_simulation_for_all_skus(sku_suppliers, leadtime_params)
    if result.empty:
        raise ValueError("No SKUs could be simulated -- check supplier/lead-time coverage.")

    _write(engine, result)

    dual_sourced_count = result["p95_leadtime_dual_days"].notna().sum()
    summary = {
        "skus_simulated": len(result),
        "skus_with_dual_source_comparison": int(dual_sourced_count),
        "skus_single_source_only": len(result) - int(dual_sourced_count),
        "mean_p95_risk_reduction_pct": round(
            result["p95_risk_reduction_pct"].dropna().mean(), 2
        ) if dual_sourced_count else None,
        "disruption_probability_assumed": DISRUPTION_PROBABILITY,
        "disruption_severity_multiplier_assumed": DISRUPTION_SEVERITY_MULTIPLIER,
    }
    logger.info("dual_sourcing_mc summary: %s", summary)
    return summary


def run(conn_str: str, **context) -> dict:
    return build_dual_sourcing_mc(conn_str)


if __name__ == "__main__":
    import os
    logging.basicConfig(level=logging.INFO)
    conn_str = os.environ.get(
        "WAREHOUSE_CONN_STRING",
        "postgresql+psycopg2://warehouse_admin:CHANGEME@postgres_warehouse:5432/resilience_radar",
    )
    print(run(conn_str))