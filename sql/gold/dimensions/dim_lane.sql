
CREATE TABLE IF NOT EXISTS gold.lane (
    lane_key              BIGINT PRIMARY KEY,
    origin_location_key      BIGINT REFERENCES location(location_key),
    dest_location_key           BIGINT REFERENCES location(location_key),
    shipping_mode                   VARCHAR,
    incoterm                           VARCHAR,
    typical_distance_km                   NUMERIC(10,2)
);