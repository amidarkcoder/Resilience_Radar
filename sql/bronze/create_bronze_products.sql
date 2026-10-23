
CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.products (
    sku                  VARCHAR,
    product_name         VARCHAR,
    category_name        VARCHAR,
    department_name      VARCHAR,
    unit_cost            NUMERIC(12,2),
    unit_weight_kg       NUMERIC(10,3),
    unit_price_msrp      NUMERIC(12,2),
    is_active            VARCHAR,          -- kept as VARCHAR ('Y'/'N'/'1'/'0') -- raw source inconsistency, normalized in silver
    catalog_snapshot_date DATE,

    _source_file          VARCHAR,
    _batch_id              VARCHAR,
    _ingested_at           TIMESTAMP DEFAULT now()
);