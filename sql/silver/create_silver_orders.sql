
CREATE TABLE IF NOT EXISTS silver.orders (
    order_line_id         VARCHAR PRIMARY KEY,
    order_id                VARCHAR NOT NULL,
    order_date                 TIMESTAMP NOT NULL,
    golden_customer_id            VARCHAR REFERENCES silver_customers(golden_customer_id),
    sku                              VARCHAR NOT NULL,
    quantity                           INTEGER CHECK (quantity > 0),
    unit_price_usd                        NUMERIC(12,2) CHECK (unit_price_usd >= 0),
    discount_pct                             NUMERIC(5,2) CHECK (discount_pct BETWEEN 0 AND 100),
    line_total_usd                              NUMERIC(14,2),

    order_status                                   VARCHAR CHECK (order_status IN
                                                       ('COMPLETE','PENDING','CANCELED','ON_HOLD','PROCESSING')),
    shipping_mode                                     VARCHAR,
    promised_transit_days                                INTEGER,
    order_region                                            VARCHAR,
    order_country                                              VARCHAR,
    market                                                        VARCHAR,
    late_delivery_risk_flag                                          BOOLEAN,   -- cast + cleaned from raw text label

    _dq_passed                                                          BOOLEAN DEFAULT TRUE,  -- set FALSE + quarantined if checks fail
    _cleaned_at                                                            TIMESTAMP DEFAULT now(),
    _batch_id                                                                VARCHAR
);