
CREATE TABLE IF NOT EXISTS gold.perfect_order (
    product_key             BIGINT REFERENCES product(product_key),
    location_key                BIGINT REFERENCES location(location_key),
    year_month                     VARCHAR(7),

    total_orders                      INTEGER,
    perfect_orders                       INTEGER,
    perfect_order_pct                       NUMERIC(6,4),

    return_rate_pct                            NUMERIC(6,4),
    damage_rate_pct                               NUMERIC(6,4),

    _computed_at                                     TIMESTAMP DEFAULT now(),

    PRIMARY KEY (product_key, location_key, year_month)
);