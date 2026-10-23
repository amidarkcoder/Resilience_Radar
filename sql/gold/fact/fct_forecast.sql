
CREATE TABLE IF NOT EXISTS gold.forecast (
    forecast_key            BIGINT PRIMARY KEY,
    product_key                BIGINT REFERENCES product(product_key),
    location_key                   BIGINT REFERENCES location(location_key),
    forecast_made_date_key             INTEGER REFERENCES date(date_key),
    target_date_key                       INTEGER REFERENCES date(date_key),
    horizon_days                             INTEGER,

    forecast_qty                                NUMERIC(12,2),
    forecast_residual_std                          NUMERIC(12,2),   -- σ_D, feeds safety stock model

    model_version                                     VARCHAR NOT NULL,
    wmape_backtest                                       NUMERIC(6,4),
    bias_backtest                                           NUMERIC(6,4),

    _loaded_at                                                 TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_fct_forecast_product_loc ON fct_forecast (product_key, location_key, model_version);
