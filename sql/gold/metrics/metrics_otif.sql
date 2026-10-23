
CREATE TABLE IF NOT EXISTS gold.otif (
    product_key             BIGINT REFERENCES product(product_key),
    location_key                BIGINT REFERENCES location(location_key),
    year_month                     VARCHAR(7),      -- 'YYYY-MM'

    total_orders                      INTEGER,
    on_time_orders                       INTEGER,
    in_full_orders                          INTEGER,
    otif_orders                                INTEGER,
    otif_pct                                      NUMERIC(6,4),

    avg_cycle_time_days                               NUMERIC(6,2),

    _computed_at                                         TIMESTAMP DEFAULT now(),

    PRIMARY KEY (product_key, location_key, year_month)
);