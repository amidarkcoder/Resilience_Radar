
CREATE TABLE IF NOT EXISTS gold.supplier (
    supplier_key          BIGINT PRIMARY KEY,
    supplier_id              VARCHAR NOT NULL,          -- natural key
    supplier_name               VARCHAR,
    supplier_country                VARCHAR,
    supplier_city                      VARCHAR,
    supplier_tier                         VARCHAR(10),
    certification_status                     VARCHAR,
    reliability_band                            VARCHAR(10),

    valid_from                                     DATE NOT NULL,
    valid_to                                          DATE NOT NULL DEFAULT '9999-12-31',
    is_current                                           BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_dim_supplier_id_current ON dim_supplier (supplier_id, is_current);