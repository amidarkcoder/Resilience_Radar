
CREATE TABLE IF NOT EXISTS gold.order_line (
    order_line_key        BIGINT PRIMARY KEY,
    order_id                 VARCHAR NOT NULL,
    date_key                    INTEGER REFERENCES date(date_key),
    product_key                    BIGINT REFERENCES product(product_key),
    customer_key                       BIGINT REFERENCES customer(customer_key),
    junk_key                               BIGINT REFERENCES junk_order_flags(junk_key),

    quantity                                  INTEGER,
    unit_price_usd                               NUMERIC(12,2),
    discount_pct                                    NUMERIC(5,2),
    line_total_usd                                     NUMERIC(14,2),

    _loaded_at                                            TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_fct_order_line_product ON fct_order_line (product_key);
CREATE INDEX idx_fct_order_line_date ON fct_order_line (date_key);