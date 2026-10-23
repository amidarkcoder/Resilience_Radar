
CREATE TABLE IF NOT EXISTS gold.product (
    product_key           BIGINT PRIMARY KEY,         -- surrogate, generated at build time
    sku                      VARCHAR NOT NULL,            -- natural key
    product_name                VARCHAR,
    category_name                   VARCHAR,
    department_name                     VARCHAR,
    unit_cost_usd                           NUMERIC(12,2),
    unit_weight_kg                              NUMERIC(10,3),
    abc_class                                      VARCHAR(1),
    xyz_class                                         VARCHAR(1),
    is_active                                            BOOLEAN,

    valid_from                                              DATE NOT NULL,
    valid_to                                                   DATE NOT NULL DEFAULT '9999-12-31',
    is_current                                                    BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_dim_product_sku_current ON dim_product (sku, is_current);