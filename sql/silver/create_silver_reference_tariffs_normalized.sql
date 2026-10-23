
CREATE TABLE IF NOT EXISTS silver.reference_tariffs_normalized (
    tariff_key             VARCHAR PRIMARY KEY,   -- hash(origin, destination, category, effective_date)
    origin_country            VARCHAR,
    destination_country          VARCHAR,
    product_category                VARCHAR,
    tariff_rate_pct                    NUMERIC(6,3),
    effective_date                        DATE,
    expiry_date                              DATE,

    _cleaned_at                                 TIMESTAMP DEFAULT now(),
    _batch_id                                     VARCHAR
);