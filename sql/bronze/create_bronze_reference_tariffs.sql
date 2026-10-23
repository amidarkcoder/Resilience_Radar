
CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.reference_tariffs (
    origin_country      VARCHAR,
    destination_country   VARCHAR,
    product_category        VARCHAR,
    tariff_rate_pct           NUMERIC(6,3),
    effective_date              DATE,
    expiry_date                   DATE,        -- NULL = currently in effect
    policy_note                    VARCHAR,

    _source_file                   VARCHAR,
    _batch_id                       VARCHAR,
    _ingested_at                     TIMESTAMP DEFAULT now()
);