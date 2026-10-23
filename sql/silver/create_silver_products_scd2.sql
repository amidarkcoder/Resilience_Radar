
CREATE TABLE IF NOT EXISTS silver.products_scd2 (
    product_version_key   VARCHAR PRIMARY KEY,   -- surrogate: hash(sku + valid_from)
    sku                     VARCHAR NOT NULL,       -- natural key
    product_name              VARCHAR,
    category_name                VARCHAR,
    department_name                 VARCHAR,
    unit_cost_usd                      NUMERIC(12,2),   -- currency-normalized via FX join
    unit_weight_kg                        NUMERIC(10,3),
    abc_class                                VARCHAR(1) CHECK (abc_class IN ('A','B','C')),
    xyz_class                                   VARCHAR(1) CHECK (xyz_class IN ('X','Y','Z')),
    is_active                                      BOOLEAN,

    row_hash                                         VARCHAR,     -- hash of tracked columns, used to detect changes on reload
    valid_from                                          DATE NOT NULL,
    valid_to                                               DATE NOT NULL DEFAULT '9999-12-31',
    is_current                                                BOOLEAN DEFAULT TRUE,

    _cleaned_at                                                  TIMESTAMP DEFAULT now(),
    _batch_id                                                      VARCHAR
);

CREATE INDEX idx_silver_products_sku_current ON silver_products_scd2 (sku, is_current);