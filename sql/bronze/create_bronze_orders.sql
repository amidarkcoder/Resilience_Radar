
CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.orders (
    order_id              VARCHAR,
    order_item_id         VARCHAR,          
    order_date             TIMESTAMP,
    customer_id             VARCHAR,
    sku                      VARCHAR,
    order_item_quantity      INTEGER,
    order_item_unit_price    NUMERIC(12,2),
    order_item_discount_pct  NUMERIC(5,2),
    order_item_total         NUMERIC(14,2),

    order_status             VARCHAR,       -- 'COMPLETE','PENDING','CANCELED','ON_HOLD', etc. — raw, uncleaned casing
    shipping_mode             VARCHAR,       -- 'Standard Class','First Class','Second Class','Same Day'
    days_for_shipment_scheduled INTEGER,     -- promised transit days
    order_region               VARCHAR,
    order_country              VARCHAR,
    market                     VARCHAR,      -- 'LATAM','USCA','Europe','Africa','Pacific Asia'
    late_delivery_risk          VARCHAR,     -- raw source label, 0/1 as text — target for Model 3

    _source_file               VARCHAR,
    _batch_id                   VARCHAR,
    _ingested_at                TIMESTAMP DEFAULT now()
);