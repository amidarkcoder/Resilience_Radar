import logging
from datetime import  timezone
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error

logger = logging.getLogger(__name__)

LAG_WEEKS = [1,2,4,8,12]
MIN_HISTORY_WEEKS =  max(LAG_WEEKS) + 4

def _fetech_weekly_demand(engine) -> pd.DataFrame:
    query = text("""
        SELECT
            sku,
            date_trunc('week', order_date)::date AS week_start,
            SUM(order_item_quantity) AS quantity
        FROM bronze.bronze_orders
        GROUP BY sku, date_trunc('week', order_date)::date
        ORDER BY sku, week_start
    """)

    ef = pd.read_sql(query, engine)
    ef['week_start'] = pd.to_datetime(ef['week_start'])
    return ef

def _build_lag_features(weekly: pd.DataFrame) -> pd.DataFrame:
    weekly = weekly.sort_values(['sku', 'week_start']).copy()
    frames = []

    for sku, grp in weekly.groupby('sku'):
        full_range = pd.date_range(grp["week_start"].min(),grp["week_start"].max(),freq="W-MON")
        grp = grp.set_index("week_start").reindex(full_range,fill_value=0)
        grp.index.name = "week_start"
        grp['sku'] = sku
        frames.append(grp.reset_index())
    weekly_full = pd.concat(frames, ignore_index=True)

    weekly_full = weekly_full.sort_values(['sku','week_start'])

    g = weekly_full.groupby('sku')['quantity']

    for lag in LAG_WEEKS:
        weekly_full[f"qty_lag_{lag}w"] = g.shift(1).rolling(lag).sum().reset_index(level=0,drop=True)
        weekly_full["target_next_week_qty"] = g.shift(-1)

    return weekly_full

def _preper_train_set(featured: pd.DataFrame) -> pd.DataFrame:
    feature_cols = [f"qty_lag_{lag}w" for lag in LAG_WEEKS]
    has_full_history = featured[feature_cols].notna().all(axis=1)
    has_label = featured["target_next_week_qty"].notna()
    return featured[has_full_history & has_label].copy()

def fit_and_forecast(conn_str: str) -> pd.DataFrame:
    engine = create_engine(conn_str)
    weekly = _fetech_weekly_demand(engine)
    if weekly.empty:
        raise ValueError(
            "no row found"
        )

    featured = _build_lag_features(weekly)
    train_set = _preper_train_set(featured)

    if len(train_set) < 50:
        raise ValueError(
            "less number of rows"
        )

    feature_col = [f"qty_lag_{lag}w" for lag in LAG_WEEKS]
    X = train_set[feature_col]
    y = train_set["target_next_week_qty"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,y,test_size=0.2,random_state=42
    )

    model = lgb.LGBMRegressor(
        objective = "regression",
        n_estimators = 200,
        max_depth = 6,
        learning_rate = 0.05,
        random_state = 42
    )
    model.fit(X_train, y_train)

    val_predictions = model.predict(X_test)
    mae = mean_absolute_error(y_test,val_predictions)
    logger.info("MAE: %.2f unit/week", mae)

    latest_per_sku = (
        featured[featured[feature_col].notna().all(axis=1)]
        .sort_values("week_start")
        .groupby("sku")
        .tail(1)
        .copy()
    )

    latest_per_sku["predicted_next_week_qty"] = model.predict(latest_per_sku[feature_col])
    latest_per_sku["forecast_week"] = latest_per_sku["week_start"] + pd.Timedelta(weeks=1)
    latest_per_sku["model_mae"] = mae
    latest_per_sku["fitted_at"] = pd.Timestamp.now()

    output_cols = ["sku","forecast_week","predicted_next_week_qty","model_mae","fitted_at"]
    forecast_df = latest_per_sku[output_cols]

    forecast_df.to_sql(
        "demand_forecast",
        engine,
        schema='silver',
        if_exists = 'replace',
        index = False
    )

    logger.info("Wrote")
    return forecast_df

def run(conn_str: str, **context) ->None:
    fit_and_forecast(conn_str)

if __name__ == "__main__":
    import os
    logging.info(level = logging.INFO)
    conn_str = os.environ.get(
        "WAREHOUSE_CONN_STRING",
        "postgresql+psycopg2://warehouse_admin:CHANGEME@postgres_warehouse:5432/resilience_radar"
    )
    fit_and_forecast(conn_str)