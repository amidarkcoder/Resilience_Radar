
CREATE TABLE IF NOT EXISTS gold.location (
    location_key          BIGINT PRIMARY KEY,
    location_id              VARCHAR NOT NULL UNIQUE,
    location_name               VARCHAR,
    location_type                  VARCHAR CHECK (location_type IN ('Plant','DC','Store','Market')),
    city                              VARCHAR,
    country                              VARCHAR,
    latitude                               NUMERIC(9,6),
    longitude                                 NUMERIC(9,6)
);