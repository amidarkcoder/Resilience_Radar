
CREATE TABLE IF NOT EXISTS silver.abc_xyz_segmentation (
    segmentation_id             VARCHAR PRIMARY KEY,
    sku                         VARCHAR NOT NULL,
    total_revenue_usd           NUMERIC(14,2),
    revenue_cum_pct             NUMERIC(6,4),
    abc_class                   VARCHAR(1) CHECK (abc_class IN ('A','B','C')),
    demand_cov                  NUMERIC(8,4),   -- coefficient of variation of demand
    xyz_class                   VARCHAR(1) CHECK (xyz_class IN ('X','Y','Z')),
    computed_at                 TIMESTAMP DEFAULT now(),
    _batch_id                   VARCHAR
);