
CREATE TABLE IF NOT EXISTS silver.fx_rates_daily (
    rate_date           DATE NOT NULL,
    currency_from          VARCHAR(3) NOT NULL,
    currency_to               VARCHAR(3) NOT NULL,
    exchange_rate                NUMERIC(14,6),
    is_forward_filled               BOOLEAN DEFAULT FALSE,   -- TRUE if gap-filled from last known rate

    _cleaned_at                        TIMESTAMP DEFAULT now(),

    PRIMARY KEY (rate_date, currency_from, currency_to)
);