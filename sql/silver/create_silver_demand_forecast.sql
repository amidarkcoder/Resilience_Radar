
CREATE TABLE IF NOT EXISTS silver.demand_forecast (
    forecast_id           VARCHAR PRIMARY KEY,
    sku                   VARCHAR NOT NULL,
    location_id           VARCHAR NOT NULL,
    forecast_made_on      DATE NOT NULL,
    target_date           DATE NOT NULL,
    horizon_days          INTEGER,
    forecast_qty          NUMERIC(12,2),
    forecast_residual_std NUMERIC(12,2),   -- σ_D -- direct input to safety stock model
    model_version         VARCHAR NOT NULL,
    wmape_backtest        NUMERIC(6,4),
    bias_backtest         NUMERIC(6,4),
    _created_at           TIMESTAMP DEFAULT now(),
    _batch_id             VARCHAR
);