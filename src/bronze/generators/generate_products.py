"""Generates bronze_products. Grain: one row per SKU catalog entry."""

import numpy as np
import pandas as pd
from faker import Faker

def generate_products(n_products: int, categories: list, unit_cost_lognormal: dict,
                       margin_multiplier_range: list, catalog_snapshot_date: str, seed: int = 42) -> pd.DataFrame:
    fake = Faker()
    rng = np.random.default_rng(seed)

    cat_names = [c["name"] for c in categories]
    cat_weights = [c["weight"] for c in categories]

    unit_cost = np.round(rng.lognormal(mean=unit_cost_lognormal["mean"],
                                        sigma=unit_cost_lognormal["sigma"], size=n_products), 2)
    multiplier = rng.uniform(*margin_multiplier_range, size=n_products)
    
    df = pd.DataFrame({
        "sku": [f"SKU-{i:04d}" for i in range(n_products)],
        "product_name": [fake.catch_phrase() for _ in range(n_products)],
        "category_name": rng.choice(cat_names, size=n_products, p=cat_weights),
        "department_name": rng.choice(["Consumer", "Commercial"], size=n_products),
        "unit_cost": unit_cost,
        "unit_weight_kg": np.round(rng.gamma(shape=2.0, scale=1.5, size=n_products), 2),
        "unit_price_msrp": np.round(unit_cost * multiplier, 2),
        # raw source inconsistency on purpose -- cleaned to proper boolean in silver
        "is_active": rng.choice(["Y", "N", "1", "0"], size=n_products, p=[0.5, 0.1, 0.35, 0.05]),
        "catalog_snapshot_date": catalog_snapshot_date,
    })
    
    return df
    