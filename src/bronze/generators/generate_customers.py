"""Generates bronze_customers. Grain: one row per raw customer record (pre-MDM)."""

import numpy as np
import pandas as pd
from faker import Faker

def generate_customers(n_customers: int, segment_weights: dict, seed: int = 42) -> pd.DataFrame:
    fake = Faker()
    Faker.seed(seed)
    rng = np.random.default_rng(seed)

    segments = list(segment_weights.keys())
    probs = list(segment_weights.values())

    rows = []
    for _ in range(n_customers):
        
        fname, lname = fake.first_name(), fake.last_name()
        rows.append({
            "customer_id": fake.uuid4(),
            "customer_fname": fname,
            "customer_lname": lname,
            "customer_email": f"{fname.lower()}.{lname.lower()}@{fake.free_email_domain()}",
            "customer_segment": rng.choice(segments, p=probs),
            "customer_city": fake.city(),
            "customer_state": fake.state_abbr(),
            "customer_country": fake.country(),
            "customer_zipcode": fake.postcode(),
            "customer_region": rng.choice(["North America", "LATAM", "EMEA", "APAC"]),
        })

    df = pd.DataFrame(rows)

    # inject near-duplicates (same person, slightly different email casing/typo)
    dupes = df.sample(frac=0.03, random_state=seed).copy()
    dupes["customer_email"] = dupes["customer_email"].str.upper()
    dupes["customer_id"] = [fake.uuid4() for _ in range(len(dupes))]
    return pd.concat([df, dupes], ignore_index=True)