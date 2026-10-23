

CREATE TABLE IF NOT EXISTS silver.inventory_snapshots (
    snapshot_date          DATE NOT NULL,
    sku                       VARCHAR NOT NULL,
    location_id                 VARCHAR NOT NULL,
    location_type                  VARCHAR,
    on_hand_qty                       INTEGER CHECK (on_hand_qty >= 0),
    on_order_qty                         INTEGER CHECK (on_order_qty >= 0),
    backorder_qty                           INTEGER CHECK (backorder_qty >= 0),
    safety_stock_target_qty                    INTEGER,
    days_of_supply                                NUMERIC(8,2),   -- computed: on_hand_qty / avg_daily_demand

    _cleaned_at                                       TIMESTAMP DEFAULT now(),
    _batch_id                                            VARCHAR,

    PRIMARY KEY (sku, location_id, snapshot_date)
);