
CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.reference_fx_rates (
    rate_date          DATE,
    currency_from        VARCHAR(3),
    currency_to            VARCHAR(3),
    exchange_rate             NUMERIC(14,6),

    _source_file              VARCHAR,
    _batch_id                  VARCHAR,
    _ingested_at                TIMESTAMP DEFAULT now()
);