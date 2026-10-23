
CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.suppliers (
    supplier_id          VARCHAR,
    supplier_name         VARCHAR,
    supplier_country       VARCHAR,
    supplier_city           VARCHAR,
    supplier_tier            VARCHAR,     -- 'Tier 1','Tier 2','Tier 3' — raw, inconsistent formatting expected
    certification_status      VARCHAR,    -- 'ISO9001','Uncertified', nullable
    onboarding_date            DATE,
    snapshot_date               DATE,     -- the date this raw record was true as of

    _source_file                VARCHAR,
    _batch_id                    VARCHAR,
    _ingested_at                 TIMESTAMP DEFAULT now()
);