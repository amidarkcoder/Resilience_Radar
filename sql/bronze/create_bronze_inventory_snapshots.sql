CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.inventory_snapshots (
    snapshot_date      DATE,
    sku                  VARCHAR,
    location_id            VARCHAR,
    location_type            VARCHAR,     -- 'DC','Plant','Store'
    on_hand_qty                INTEGER,
    on_order_qty                 INTEGER,
    backorder_qty                  INTEGER,
    safety_stock_target_qty          INTEGER,   -- as currently configured in WMS (pre-your-model baseline)

    _source_file                     VARCHAR,
    _batch_id                         VARCHAR,
    _ingested_at                       TIMESTAMP DEFAULT now()
);