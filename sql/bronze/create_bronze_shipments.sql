
CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.shipments (
    shipment_id         VARCHAR,
    order_id             VARCHAR,
    ship_date             TIMESTAMP,
    delivery_date           TIMESTAMP,
    origin_location           VARCHAR,
    destination_location        VARCHAR,
    shipping_mode                 VARCHAR,
    carrier_name                   VARCHAR,
    freight_cost                     NUMERIC(12,2),
    distance_km                        NUMERIC(10,2),
    transit_days_actual                  INTEGER,

    _source_file                         VARCHAR,
    _batch_id                             VARCHAR,
    _ingested_at                           TIMESTAMP DEFAULT now()
);