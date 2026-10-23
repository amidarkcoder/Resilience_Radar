
CREATE TABLE IF NOT EXISTS silver.shipments (
    shipment_id           VARCHAR PRIMARY KEY,
    order_id                VARCHAR NOT NULL,
    ship_date                  TIMESTAMP NOT NULL,
    delivery_date                 TIMESTAMP,
    origin_location                  VARCHAR,
    destination_location                VARCHAR,
    shipping_mode                          VARCHAR,
    carrier_name_std                          VARCHAR,     -- standardized carrier name (dedup of 'FedEx'/'Fed Ex'/'FEDEX')
    freight_cost_usd                             NUMERIC(12,2),
    distance_km                                     NUMERIC(10,2),
    transit_days_actual                                INTEGER CHECK (transit_days_actual >= 0),

    _dq_passed                                            BOOLEAN DEFAULT TRUE,
    _cleaned_at                                               TIMESTAMP DEFAULT now(),
    _batch_id                                                   VARCHAR
);  