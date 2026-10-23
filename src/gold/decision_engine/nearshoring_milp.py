import logging

import pandas as pd
import pulp
from sqlalchemy import create_engine, text, inspect

logger = logging.getLogger(__name__)

# PLACEHOLDER -- correct against your actual generator's country values.
NEARSHORE_COUNTRIES = {"United States", "Mexico", "Canada"}

# How much worse (in %) the optimizer is allowed to make aggregate
# lead-time exposure relative to the as-is baseline. 0.0 = no worse at all.
RESILIENCE_SLACK_PCT = 0.0

SOLVER_TIME_LIMIT_SECONDS = 120


def _assert_sources_exist(engine) -> None:
    inspector = inspect(engine)
    silver_tables = inspector.get_table_names(schema="silver")
    missing = [t for t in ("orders", "supplier_leadtime_params") if t not in silver_tables]
    if missing:
        raise RuntimeError(
            f"Missing required silver table(s): {missing}. Run clean_orders.py "
            "and leadtime_distribution.py (via silver_processing DAG) first."
        )


def _fetch_sku_supplier_costs(engine) -> pd.DataFrame:
    """
    Average unit cost per (sku, supplier) pair, with the supplier's
    origin_country carried through for near/far classification.
    """
    query = text("""
        SELECT
            sku,
            supplier_id,
            origin_country,
            AVG(unit_cost_at_po) AS avg_unit_cost,
            COUNT(*) AS line_count
        FROM bronze.bronze_purchase_orders
        GROUP BY sku, supplier_id, origin_country
    """)
    return pd.read_sql(query, engine)


def _fetch_leadtime_params(engine) -> pd.DataFrame:
    query = text("SELECT supplier_id, mean_lead_time_days as mean_lead_time_days FROM silver.supplier_leadtime_params")
    return pd.read_sql(query, engine).set_index("supplier_id")["mean_lead_time_days"]


def _fetch_sku_demand_weights(engine) -> pd.Series:
    query = text("""
        SELECT sku, SUM(order_item_quantity) AS total_qty
        FROM silver.orders
        GROUP BY sku
    """)
    df = pd.read_sql(query, engine)
    return df.set_index("sku")["total_qty"]


def _classify_near_far(origin_country: str) -> str:
    return "near" if origin_country in NEARSHORE_COUNTRIES else "far"


def _determine_current_primary_supplier(cost_df: pd.DataFrame) -> pd.DataFrame:
    sorted_df = cost_df.sort_values(
        ["sku", "line_count", "supplier_id"], ascending=[True, False, True]
    )
    return sorted_df.drop_duplicates(subset="sku", keep="first")[["sku", "supplier_id"]].rename(
        columns={"supplier_id": "current_supplier_id"}
    )


def _build_and_solve_milp(
    cost_df: pd.DataFrame, leadtime: pd.Series, demand: pd.Series, current_primary: pd.DataFrame
) -> pd.DataFrame:
    cost_df = cost_df[cost_df["supplier_id"].isin(leadtime.index)].copy()
    cost_df = cost_df[cost_df["sku"].isin(demand.index)].copy()
    cost_df["lead_time_days"] = cost_df["supplier_id"].map(leadtime)
    cost_df["demand_qty"] = cost_df["sku"].map(demand)
    cost_df["near_far"] = cost_df["origin_country"].apply(_classify_near_far)

    skus = cost_df["sku"].unique().tolist()

    # Baseline: aggregate demand-weighted lead-time exposure under current
    # as-is primary sourcing, used as the resilience constraint's ceiling.
    baseline = current_primary.merge(
        cost_df[["sku", "supplier_id", "lead_time_days", "demand_qty"]],
        left_on=["sku", "current_supplier_id"],
        right_on=["sku", "supplier_id"],
        how="inner",
    )
    baseline_exposure = (baseline["lead_time_days"] * baseline["demand_qty"]).sum()
    exposure_cap = baseline_exposure * (1 + RESILIENCE_SLACK_PCT)

    prob = pulp.LpProblem("nearshoring_optimization", pulp.LpMinimize)

    x = {}
    for _, row in cost_df.iterrows():
        key = (row["sku"], row["supplier_id"])
        x[key] = pulp.LpVariable(f"x_{row['sku']}_{row['supplier_id']}", cat="Binary")

    # Objective: minimize total sourcing cost (unit cost * demand volume).
    prob += pulp.lpSum(
        x[(row["sku"], row["supplier_id"])] * row["avg_unit_cost"] * row["demand_qty"]
        for _, row in cost_df.iterrows()
    )

    # Constraint 1: exactly one supplier chosen per SKU.
    for sku in skus:
        candidates = cost_df[cost_df["sku"] == sku]
        prob += pulp.lpSum(x[(sku, s)] for s in candidates["supplier_id"]) == 1, f"one_supplier_{sku}"

    # Constraint 2: aggregate lead-time exposure must not exceed baseline.
    prob += pulp.lpSum(
        x[(row["sku"], row["supplier_id"])] * row["lead_time_days"] * row["demand_qty"]
        for _, row in cost_df.iterrows()
    ) <= exposure_cap, "resilience_cap"

    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=SOLVER_TIME_LIMIT_SECONDS)
    prob.solve(solver)

    status = pulp.LpStatus[prob.status]
    logger.info("MILP solve status: %s", status)
    if status not in ("Optimal", "Not Solved"):
        logger.warning(
            "Solver did not reach a clean optimal solution (status=%s). "
            "Results below may be infeasible or a best-effort partial solution.",
            status,
        )

    results = []
    for _, row in cost_df.iterrows():
        var = x[(row["sku"], row["supplier_id"])]
        if var.value() == 1:
            results.append(row)

    chosen = pd.DataFrame(results)
    chosen = chosen.merge(current_primary, on="sku", how="left")
    chosen["sourcing_changed"] = chosen["supplier_id"] != chosen["current_supplier_id"]
    chosen = chosen.rename(columns={"supplier_id": "recommended_supplier_id"})

    summary_meta = {
        "solver_status": status,
        "baseline_leadtime_exposure_days": round(baseline_exposure, 1),
        "resilience_exposure_cap_days": round(exposure_cap, 1),
    }
    chosen.attrs["summary_meta"] = summary_meta
    return chosen


def _write(engine, df: pd.DataFrame) -> None:
    output_cols = [
        "sku", "recommended_supplier_id", "current_supplier_id", "sourcing_changed",
        "near_far", "avg_unit_cost", "lead_time_days", "demand_qty",
    ]
    output = df[output_cols].copy()
    output["built_at"] = pd.Timestamp.now()
    output.to_sql("nearshoring_milp", engine, schema="gold", if_exists="replace", index=False)
    logger.info("Wrote %d SKU sourcing recommendations to gold.nearshoring_milp", len(output))


def build_nearshoring_milp(conn_str: str) -> dict:
    engine = create_engine(conn_str)
    _assert_sources_exist(engine)

    cost_df = _fetch_sku_supplier_costs(engine)
    if cost_df.empty:
        raise ValueError("No rows returned from bronze.bronze_purchase_orders.")

    leadtime = _fetch_leadtime_params(engine)
    if leadtime.empty:
        raise ValueError("silver.supplier_leadtime_params is empty -- run leadtime_distribution.py first.")

    demand = _fetch_sku_demand_weights(engine)
    if demand.empty:
        raise ValueError("No demand weights computed from silver.orders.")

    current_primary = _determine_current_primary_supplier(cost_df)

    result = _build_and_solve_milp(cost_df, leadtime, demand, current_primary)
    if result.empty:
        raise ValueError("MILP produced no feasible assignment -- check solver status in logs.")

    _write(engine, result)

    summary = {
        "skus_optimized": len(result),
        "skus_recommended_to_change_supplier": int(result["sourcing_changed"].sum()),
        **result.attrs["summary_meta"],
    }
    logger.info("nearshoring_milp summary: %s", summary)
    return summary


def run(conn_str: str, **context) -> dict:
    return build_nearshoring_milp(conn_str)


if __name__ == "__main__":
    import os
    logging.basicConfig(level=logging.INFO)
    conn_str = os.environ.get(
        "WAREHOUSE_CONN_STRING",
        "postgresql+psycopg2://warehouse_admin:CHANGEME@postgres_warehouse:5432/resilience_radar",
    )
    print(run(conn_str))