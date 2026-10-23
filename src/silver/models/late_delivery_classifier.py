import logging
from datetime import timezone

import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, precision_score, recall_score
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)

CATEGORICAL_COLS = ["shipping_mode", "order_region", "market", "order_status"]
NUMERIC_COLS = [
    "days_for_shipment_scheduled",
    "order_item_quantity",
    "order_item_discount_pct",
    "order_item_unit_price",
]
LABEL_COL = "late_delivery_risk"
MIN_TRAINABLE_ROWS = 100


def _fetch_orders(engine) -> pd.DataFrame:
    query = text(f"""
        SELECT
            order_item_id,
            shipping_mode,
            days_for_shipment_scheduled,
            order_item_quantity,
            order_item_discount_pct,
            order_item_unit_price,
            order_region,
            market,
            order_status,
            {LABEL_COL}
        FROM bronze.bronze_orders
    """)
    df = pd.read_sql(query, engine)
    df[LABEL_COL] = pd.to_numeric(df[LABEL_COL], errors="coerce")
    return df


def _encode_categoricals(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:

    df = df.copy()
    for col in CATEGORICAL_COLS:
        df[col] = df[col].astype("category")
    encoded = pd.get_dummies(df, columns=CATEGORICAL_COLS, dummy_na=False) ##one-hot-encoding
    category_map = {col: df[col].cat.categories.tolist() for col in CATEGORICAL_COLS}
    return encoded, category_map


def fit_and_score(conn_str: str) -> pd.DataFrame:
    engine = create_engine(conn_str)

    raw = _fetch_orders(engine)
    if raw.empty:
        raise ValueError(
            "No rows returned from bronze.orders -- check bronze_ingestion has run."
        )

    raw = raw.dropna(subset=[LABEL_COL])
    if len(raw) < MIN_TRAINABLE_ROWS:
        raise ValueError(
            f"Only {len(raw)} labeled rows available -- need at least "
            f"{MIN_TRAINABLE_ROWS} to train a meaningful classifier."
        )

    encoded, _ = _encode_categoricals(raw)

    feature_cols = NUMERIC_COLS + [
        c for c in encoded.columns
        if any(c.startswith(f"{cat}_") for cat in CATEGORICAL_COLS)
    ]
    X = encoded[feature_cols]
    y = encoded[LABEL_COL].astype(int)

    X_train, X_test, y_train, y_test, idx_train, idx_test = train_test_split(
        X, y, encoded["order_item_id"], test_size=0.2, random_state=42, stratify=y
    )

    model = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=200,
        max_depth=6,
        learning_rate=0.05,
        random_state=42,
    )
    model.fit(X_train, y_train)

    test_probs = model.predict(X_test, raw_score=False)  # predicted labels
    test_proba = model.predict_proba(X_test)[:, 1]        # predicted probabilities

    auc = roc_auc_score(y_test, test_proba)
    precision = precision_score(y_test, test_probs)
    recall = recall_score(y_test, test_probs)
    logger.info(
        "Late-delivery classifier trained. Validation AUC=%.3f precision=%.3f recall=%.3f",
        auc, precision, recall,
    )

    # Score ALL rows (not just the held-out test split) for the output table,
    # since downstream consumers need risk scores for every order line, not
    # just the ones randomly assigned to the test split.
    all_proba = model.predict_proba(X)[:, 1]
    all_pred_class = (all_proba >= 0.5).astype(int)

    scores_df = pd.DataFrame({
        "order_item_id": encoded["order_item_id"],
        "predicted_late_delivery_probability": all_proba,
        "predicted_late_delivery_flag": all_pred_class,
        "actual_late_delivery_risk": y.values,
        "model_auc": auc,
        "model_precision": precision,
        "model_recall": recall,
        "fitted_at": pd.Timestamp.now(tz=timezone.utc),
    })

    scores_df.to_sql(
        "late_delivery_risk_scores",
        engine,
        schema="silver",
        if_exists="replace",
        index=False,
    )

    logger.info("Wrote %d risk scores to silver.late_delivery_risk_scores", len(scores_df))
    return scores_df


def run(conn_str: str, **context) -> None:
    """Airflow-callable entrypoint, matching the run(conn_str, **context)
    pattern used across all silver model files in this project.
    """
    fit_and_score(conn_str)


if __name__ == "__main__":
    import os
    logging.basicConfig(level=logging.INFO)
    conn_str = os.environ.get(
        "WAREHOUSE_CONN_STRING",
        "postgresql+psycopg2://warehouse_admin:CHANGEME@postgres_warehouse:5432/resilience_radar",
    )
    fit_and_score(conn_str)