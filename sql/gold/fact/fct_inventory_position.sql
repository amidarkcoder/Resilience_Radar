
CREATE TABLE IF NOT EXISTS gold.inventory_position (
    product_key            BIGINT REFERENCES product(product_key),
    location_key               BIGINT REFERENCES location(location_key),
    date_key                       INTEGER REFERENCES date(date_key),

    on_hand_qty                       INTEGER,
    on_order_qty                         INTEGER,
    backorder_qty                           INTEGER,
    safety_stock_target_qty                    INTEGER,
    days_of_supply                                NUMERIC(8,2),

    PRIMARY KEY (product_key, location_key, date_key)
);

CREATE INDEX idx_fct_inventory_date ON fct_inventory_position (date_key);