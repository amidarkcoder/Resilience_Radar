"""Generates bronze_suppliers. Grain: one row per supplier snapshot record."""

import numpy as np
import pandas as pd
from faker import Faker

def generate_suppliers(n_suppliers: int, tier_weights: dict, countries: list,
                        snapshot_date: str, seed: int = 42) -> pd.DataFrame:
    fake = Faker()
    rng = np.random.default_rng(seed)

    tiers = list(tier_weights.keys())
    tier_probs = list(tier_weights.values())

    onboarding_dates = pd.to_datetime(
        rng.choice(pd.date_range("2015-01-01", snapshot_date), size=n_suppliers)
    )

    df = pd.DataFrame({
        "supplier_id": [f"SUP-{i:04d}" for i in range(n_suppliers)],
        "supplier_name": [fake.company() for _ in range(n_suppliers)],
        "supplier_country": rng.choice(countries, size=n_suppliers),
        "supplier_city": [fake.city() for _ in range(n_suppliers)],
        "supplier_tier": rng.choice(tiers, size=n_suppliers, p=tier_probs),
        "certification_status": rng.choice(["ISO9001", "Uncertified", "ISO14001"],
                                            size=n_suppliers, p=[0.5, 0.35, 0.15]),
        "onboarding_date": onboarding_dates,
        "snapshot_date": snapshot_date,
    })
    return df