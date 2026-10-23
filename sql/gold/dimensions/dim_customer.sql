
CREATE TABLE IF NOT EXISTS gold.customer (
    customer_key          BIGINT PRIMARY KEY,
    golden_customer_id       VARCHAR NOT NULL UNIQUE,   -- natural key, from silver MDM output
    customer_full_name          VARCHAR,
    customer_segment               VARCHAR,
    customer_city                     VARCHAR,
    customer_state                       VARCHAR,
    customer_country                        VARCHAR,
    customer_region                            VARCHAR
);