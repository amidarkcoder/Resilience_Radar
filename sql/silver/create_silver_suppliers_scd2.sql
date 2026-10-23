
CREATE TABLE IF NOT EXISTS silver.suppliers_scd2 (
    supplier_version_key   VARCHAR PRIMARY KEY,   -- surrogate: hash(supplier_id + valid_from)
    supplier_id              VARCHAR NOT NULL,       -- natural key
    supplier_name               VARCHAR,
    supplier_country                VARCHAR,
    supplier_city                      VARCHAR,
    supplier_tier                         VARCHAR(10) CHECK (supplier_tier IN ('Tier 1','Tier 2','Tier 3')),
    certification_status                     VARCHAR,
    reliability_band                            VARCHAR(10),   -- 'High','Medium','Low' -- computed from historical on-time %

    row_hash                                       VARCHAR,
    valid_from                                        DATE NOT NULL,
    valid_to                                             DATE NOT NULL DEFAULT '9999-12-31',
    is_current                                              BOOLEAN DEFAULT TRUE,

    _cleaned_at                                                TIMESTAMP DEFAULT now(),
    _batch_id                                                    VARCHAR
);

CREATE INDEX idx_silver_suppliers_id_current ON silver_suppliers_scd2 (supplier_id, is_current);