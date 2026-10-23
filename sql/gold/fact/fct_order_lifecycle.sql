
CREATE TABLE IF NOT EXISTS gold.order_lifecycle (
    order_id                     VARCHAR PRIMARY KEY,
    customer_key                    BIGINT REFERENCES customer(customer_key),

    placed_date_key                     INTEGER REFERENCES date(date_key),
    picked_date_key                        INTEGER REFERENCES date(date_key),
    packed_date_key                           INTEGER REFERENCES date(date_key),
    shipped_date_key                             INTEGER REFERENCES date(date_key),
    delivered_date_key                              INTEGER REFERENCES date(date_key),
    promised_date_key                                  INTEGER REFERENCES date(date_key),

    days_placed_to_picked                                 NUMERIC(6,2),
    days_picked_to_shipped                                   NUMERIC(6,2),
    days_shipped_to_delivered                                   NUMERIC(6,2),
    total_cycle_time_days                                          NUMERIC(6,2),

    ordered_qty                                                       INTEGER,
    delivered_qty                                                        INTEGER,
    is_on_time                                                              BOOLEAN,   -- delivered_date <= promised_date
    is_in_full                                                                 BOOLEAN,   -- delivered_qty >= ordered_qty
    otif_flag                                                                     BOOLEAN,   -- on_time AND in_full
    perfect_order_flag                                                               BOOLEAN,   -- OTIF + no damage/no return

    lifecycle_status                                                                    VARCHAR,   -- 'IN_PROGRESS','COMPLETE','RETURNED'
    _last_updated_at                                                                       TIMESTAMP DEFAULT now()
);