
CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.order_lifecycle_events (
    event_id        VARCHAR,
    order_id        VARCHAR,
    event_type      VARCHAR,       -- 'PLACED','PICKED','PACKED','SHIPPED','DELIVERED','RETURNED'
    event_timestamp TIMESTAMP,
    event_location  VARCHAR,
    promised_date   DATE,          -- repeated on every event row in raw source (denormalized, as real systems do)

    _source_file     VARCHAR,
    _batch_id         VARCHAR,
    _ingested_at      TIMESTAMP DEFAULT now()
);
