
CREATE TABLE IF NOT EXISTS gold.shipment (
    shipment_key           BIGINT PRIMARY KEY,
    order_id                  VARCHAR,
    lane_key                     BIGINT REFERENCES lane(lane_key),
    ship_date_key                   INTEGER REFERENCES date(date_key),
    delivery_date_key                   INTEGER REFERENCES date(date_key),

    carrier_name_std                       VARCHAR,
    freight_cost_usd                           NUMERIC(12,2),
    distance_km                                   NUMERIC(10,2),
    transit_days_actual                              INTEGER,

    _loaded_at                                          TIMESTAMP DEFAULT now()
);
