"""Orchestrates Stage 1: generates all synthetic bronze data and loads it into
the warehouse. Designed to be called as a single Airflow task, or standalone
via `python -m src.bronze.load_bronze`.
"""

import uuid
import yaml
from pathlib import Path
from sqlalchemy import create_engine

from src.bronze.generators import (
    generate_customers, generate_products, generate_orders,
    generate_order_lifecycle_events, generate_suppliers,
    generate_purchase_orders, generate_shipments,
    generate_inventory_snapshots, generate_reference_data,
)

CONFIG_PATH = Path(__file__).parent / "config" / "generation_params.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def run(conn_str: str = "postgresql://airflow:airflow@postgres:5432/resilience_radar", **context):
    cfg = load_config()
    g = cfg["global"]
    batch_id = context.get("run_id", str(uuid.uuid4()))
    engine = create_engine(conn_str)

    def _write(df, table_name,schema="bronze"):
        df["_batch_id"] = batch_id
        df["_source_file"] = "synthetic_generator"
        df.to_sql(table_name, engine, schema=schema, if_exists="append", index=False)
        print(f"[bronze] loaded {len(df):>7} rows -> {table_name}")

    # 1. independent base dimensions
    customers_df = generate_customers.generate_customers(
        cfg["customers"]["n_customers"], cfg["customers"]["segment_weights"], g["seed"])
    _write(customers_df, "bronze_customers")

    products_df = generate_products.generate_products(
        cfg["products"]["n_products"], cfg["products"]["categories"],
        cfg["products"]["unit_cost_lognormal"], cfg["products"]["margin_multiplier_range"],
        g["end_date"], g["seed"])
    _write(products_df, "bronze_products")

    suppliers_df = generate_suppliers.generate_suppliers(
        cfg["suppliers"]["n_suppliers"], cfg["suppliers"]["tier_weights"],
        cfg["suppliers"]["countries"], g["end_date"], g["seed"])
    _write(suppliers_df, "bronze_suppliers")

    # 2. tables dependent on step 1
    orders_df = generate_orders.generate_orders(
        customers_df, products_df, cfg["orders"]["n_order_lines"], g["start_date"], g["end_date"],
        cfg["orders"]["quantity_poisson_lambda"], cfg["orders"]["discount_beta_params"],
        cfg["orders"]["shipping_mode_weights"], cfg["orders"]["order_status_weights"],
        cfg["orders"]["promised_days_weights"], cfg["orders"]["markets"], g["seed"])
    _write(orders_df, "bronze_orders")

    lifecycle_df = generate_order_lifecycle_events.generate_order_lifecycle_events(orders_df, seed=g["seed"])
    _write(lifecycle_df, "bronze_order_lifecycle_events")

    po_df = generate_purchase_orders.generate_purchase_orders(
        suppliers_df, products_df, cfg["purchase_orders"]["n_po_lines"], g["start_date"], g["end_date"],
        cfg["purchase_orders"]["reliability_tiers"], cfg["purchase_orders"]["incoterms"],
        cfg["purchase_orders"]["freight_modes_weights"], g["seed"])
    _write(po_df, "bronze_purchase_orders")

    shipments_df = generate_shipments.generate_shipments(
        orders_df, cfg["shipments"]["carrier_names"], cfg["shipments"]["transit_days_lognormal"], g["seed"])
    _write(shipments_df, "bronze_shipments")

    inventory_df = generate_inventory_snapshots.generate_inventory_snapshots(
        products_df, cfg["inventory_snapshots"]["n_locations"], g["start_date"], g["end_date"],
        cfg["inventory_snapshots"]["initial_stock_days_of_supply"], g["seed"])
    _write(inventory_df, "bronze_inventory_snapshots")

    # 3. independent reference data
    tariffs_df = generate_reference_data.generate_tariffs(
        cfg["reference_data"]["tariff_categories"], cfg["suppliers"]["countries"], seed=g["seed"])
    _write(tariffs_df, "bronze_reference_tariffs")

    fx_df = generate_reference_data.generate_fx_rates(
        cfg["reference_data"]["currencies"], g["start_date"], g["end_date"], g["seed"])
    _write(fx_df, "bronze_reference_fx_rates")

    calendar_df = generate_reference_data.generate_calendar(
        cfg["reference_data"]["holiday_countries"], g["start_date"], g["end_date"])
    _write(calendar_df, "bronze_reference_calendar")

    print(f"[bronze] batch {batch_id} complete.")


if __name__ == "__main__":
    run()