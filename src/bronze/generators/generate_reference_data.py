"""Generates bronze_reference_tariffs, bronze_reference_fx_rates, bronze_reference_calendar.

Three independent small reference datasets -- not synthetic noise, but
structured to resemble real trade-policy / FX / holiday data.
"""

import numpy as np
import pandas as pd

def generate_tariffs(tariff_categories: list, origin_countries: list,
                      destination_country: str = "USA", seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for origin in origin_countries:
        for category in tariff_categories:
            rate = round(float(rng.uniform(0, 25)), 2)
            rows.append({
                "origin_country": origin, "destination_country": destination_country,
                "product_category": category, "tariff_rate_pct": rate,
                "effective_date": "2023-01-01", "expiry_date": None,
                "policy_note": "synthetic baseline rate",
            })
    return pd.DataFrame(rows)

def generate_fx_rates(currencies: list, start_date: str, end_date: str, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start_date, end_date, freq="D")
    rows = []
    for ccy in currencies:
        rate = rng.uniform(0.1, 7.0)   # arbitrary plausible starting FX rate vs USD
        for d in dates:
            rate *= (1 + rng.normal(0, 0.002))   # small daily random walk
            rows.append({"rate_date": d, "currency_from": ccy, "currency_to": "USD",
                         "exchange_rate": round(rate, 6)})
    return pd.DataFrame(rows)

def generate_calendar(countries: list, start_date: str, end_date: str) -> pd.DataFrame:
    import holidays as holidays_lib
    dates = pd.date_range(start_date, end_date, freq="D")
    rows = []
    for country in countries:
        country_holidays = holidays_lib.country_holidays(country)
        for d in dates:
            rows.append({
                "calendar_date": d, "country": country,
                "is_holiday": d in country_holidays,
                "holiday_name": country_holidays.get(d),
                "is_weekend": d.weekday() >= 5,
                "fiscal_year": d.year, "fiscal_period": d.month,
            })
    return pd.DataFrame(rows)