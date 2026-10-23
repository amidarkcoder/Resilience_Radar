
CREATE TABLE IF NOT EXISTS silver.order_lifecycle (
    event_id            VARCHAR PRIMARY KEY,
    order_id              VARCHAR NOT NULL,
    event_type               VARCHAR CHECK (event_type IN
                                ('PLACED','PICKED','PACKED','SHIPPED','DELIVERED','RETURNED')),
    event_timestamp             TIMESTAMP NOT NULL,
    event_location                 VARCHAR,
    promised_date                     DATE,

    _dedup_key                           VARCHAR,     -- hash(order_id, event_type) -- used to drop exact re-sent duplicate events
    _cleaned_at                             TIMESTAMP DEFAULT now(),
    _batch_id                                 VARCHAR
);

CREATE INDEX idx_silver_lifecycle_order ON silver_order_lifecycle (order_id, event_timestamp);