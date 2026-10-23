CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.customers (
    customer_id         VARCHAR,
    customer_fname      VARCHAR,
    customer_lname      VARCHAR,
    customer_email      VARCHAR,
    customer_segment    VARCHAR,          -- 'Consumer', 'Corporate', 'Home Office'
    customer_city       VARCHAR,
    customer_state      VARCHAR,
    customer_country    VARCHAR,
    customer_zipcode    VARCHAR,          -- VARCHAR on purpose: real zip data has leading zeros, alpha chars (UK/CA)
    customer_region     VARCHAR,

    _source_file         VARCHAR,
    _batch_id             VARCHAR,
    _ingested_at          TIMESTAMP DEFAULT now()
);