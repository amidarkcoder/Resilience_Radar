

CREATE TABLE IF NOT EXISTS gold.supplier_tier (
    bridge_key               BIGINT PRIMARY KEY,
    supplier_key                 BIGINT REFERENCES supplier(supplier_key),
    upstream_supplier_key           BIGINT REFERENCES supplier(supplier_key),
    tier_level                         INTEGER CHECK (tier_level >= 1),   -- 1 = direct, 2 = sub-supplier, etc.

    UNIQUE (supplier_key, upstream_supplier_key, tier_level)
);