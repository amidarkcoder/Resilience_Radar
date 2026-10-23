CREATE SCHEMA IF NOT EXISTS silver;


CREATE TABLE IF NOT EXISTS silver.customers (
    golden_customer_id            VARCHAR PRIMARY KEY,   -- surrogate, generated after fuzzy match clustering
    customer_full_name            VARCHAR,
    customer_email                VARCHAR,
    customer_segment              VARCHAR CHECK (customer_segment IN ('Consumer','Corporate','Home Office')),
    customer_city                 VARCHAR,
    customer_state                VARCHAR,
    customer_country              VARCHAR,
    customer_region               VARCHAR,
    source_customer_ids_merged    VARCHAR[],  -- audit trail: which bronze IDs collapsed into this golden record
    match_confidence_score        NUMERIC(4,3),  -- fuzzy-match score, 0-1, for QA review of low-confidence merges
    _cleaned_at                   TIMESTAMP DEFAULT now(),
    _batch_id                     VARCHAR
);

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

CREATE TABLE IF NOT EXISTS silver.orders (
    order_line_id         VARCHAR PRIMARY KEY,
    order_id                VARCHAR NOT NULL,
    order_date                 TIMESTAMP NOT NULL,
    golden_customer_id            VARCHAR REFERENCES silver_customers(golden_customer_id),
    sku                              VARCHAR NOT NULL,
    quantity                           INTEGER CHECK (quantity > 0),
    unit_price_usd                        NUMERIC(12,2) CHECK (unit_price_usd >= 0),
    discount_pct                             NUMERIC(5,2) CHECK (discount_pct BETWEEN 0 AND 100),
    line_total_usd                              NUMERIC(14,2),

    order_status                                   VARCHAR CHECK (order_status IN
                                                       ('COMPLETE','PENDING','CANCELED','ON_HOLD','PROCESSING')),
    shipping_mode                                     VARCHAR,
    promised_transit_days                                INTEGER,
    order_region                                            VARCHAR,
    order_country                                              VARCHAR,
    market                                                        VARCHAR,
    late_delivery_risk_flag                                          BOOLEAN,   -- cast + cleaned from raw text label

    _dq_passed                                                          BOOLEAN DEFAULT TRUE,  -- set FALSE + quarantined if checks fail
    _cleaned_at                                                            TIMESTAMP DEFAULT now(),
    _batch_id                                                                VARCHAR
);

CREATE TABLE IF NOT EXISTS silver.order_lifecycle (
    event_id            VARCHAR PRIMARY KEY,
    order_id              VARCHAR NOT NULL,
    event_type               VARCHAR CHECK (event_type IN
                                ('PLACED','PICKED','PACKED','SHIPPED','DELIVERED','RETURNED')),
    event_timestamp             TIMESTAMP NOT NULL,
    event_location                 VARCHAR,
    promised_date                     DATE,

    _dedup_key                           VARCHAR,     -- hash(order_id, event_type) -- used to drop exact re-sent duplicate events
    _cleaned_at                             TIMESTAMP DEFAULT now(),
    _batch_id                                 VARCHAR
);

CREATE INDEX idx_silver_lifecycle_order ON silver_order_lifecycle (order_id, event_timestamp);

CREATE TABLE IF NOT EXISTS silver.purchase_orders (
    po_line_id              VARCHAR PRIMARY KEY,
    po_id                      VARCHAR NOT NULL,
    supplier_version_key          VARCHAR REFERENCES silver_suppliers_scd2(supplier_version_key),
    sku                              VARCHAR NOT NULL,
    po_date                            DATE NOT NULL,
    promised_delivery_date                DATE NOT NULL,
    actual_delivery_date                     DATE,          -- NULL = still open/in transit

    promised_lead_time_days                     INTEGER,    -- promised_delivery_date - po_date
    actual_lead_time_days                          INTEGER, -- NULL if still open
    lead_time_variance_days                           INTEGER,
    is_po_open                                           BOOLEAN,   -- TRUE if actual_delivery_date IS NULL

    po_quantity                                             INTEGER CHECK (po_quantity > 0),
    unit_cost_usd                                              NUMERIC(12,2),  -- FX-normalized from bronze's local currency
    incoterm                                                      VARCHAR,
    freight_mode                                                     VARCHAR,
    origin_country                                                      VARCHAR,
    destination_country                                                    VARCHAR,
    po_status                                                                 VARCHAR,

    _dq_passed                                                                   BOOLEAN DEFAULT TRUE,
    _cleaned_at                                                                     TIMESTAMP DEFAULT now(),
    _batch_id                                                                         VARCHAR
);

CREATE INDEX idx_silver_po_supplier ON silver_purchase_orders (supplier_version_key);

CREATE TABLE IF NOT EXISTS silver.shipments (
    shipment_id           VARCHAR PRIMARY KEY,
    order_id                VARCHAR NOT NULL,
    ship_date                  TIMESTAMP NOT NULL,
    delivery_date                 TIMESTAMP,
    origin_location                  VARCHAR,
    destination_location                VARCHAR,
    shipping_mode                          VARCHAR,
    carrier_name_std                          VARCHAR,     -- standardized carrier name (dedup of 'FedEx'/'Fed Ex'/'FEDEX')
    freight_cost_usd                             NUMERIC(12,2),
    distance_km                                     NUMERIC(10,2),
    transit_days_actual                                INTEGER CHECK (transit_days_actual >= 0),

    _dq_passed                                            BOOLEAN DEFAULT TRUE,
    _cleaned_at                                               TIMESTAMP DEFAULT now(),
    _batch_id                                                   VARCHAR
); 

CREATE TABLE IF NOT EXISTS silver.inventory_snapshots (
    snapshot_date          DATE NOT NULL,
    sku                       VARCHAR NOT NULL,
    location_id                 VARCHAR NOT NULL,
    location_type                  VARCHAR,
    on_hand_qty                       INTEGER CHECK (on_hand_qty >= 0),
    on_order_qty                         INTEGER CHECK (on_order_qty >= 0),
    backorder_qty                           INTEGER CHECK (backorder_qty >= 0),
    safety_stock_target_qty                    INTEGER,
    days_of_supply                                NUMERIC(8,2),   -- computed: on_hand_qty / avg_daily_demand

    _cleaned_at                                       TIMESTAMP DEFAULT now(),
    _batch_id                                            VARCHAR,

    PRIMARY KEY (sku, location_id, snapshot_date)
);

CREATE TABLE IF NOT EXISTS silver.reference_tariffs_normalized (
    tariff_key             VARCHAR PRIMARY KEY,   -- hash(origin, destination, category, effective_date)
    origin_country            VARCHAR,
    destination_country          VARCHAR,
    product_category                VARCHAR,
    tariff_rate_pct                    NUMERIC(6,3),
    effective_date                        DATE,
    expiry_date                              DATE,

    _cleaned_at                                 TIMESTAMP DEFAULT now(),
    _batch_id                                     VARCHAR
);

CREATE TABLE IF NOT EXISTS silver.fx_rates_daily (
    rate_date           DATE NOT NULL,
    currency_from          VARCHAR(3) NOT NULL,
    currency_to               VARCHAR(3) NOT NULL,
    exchange_rate                NUMERIC(14,6),
    is_forward_filled               BOOLEAN DEFAULT FALSE,   -- TRUE if gap-filled from last known rate

    _cleaned_at                        TIMESTAMP DEFAULT now(),

    PRIMARY KEY (rate_date, currency_from, currency_to)
);

CREATE TABLE IF NOT EXISTS silver.supplier_leadtime_params (
    leadtime_model_id      VARCHAR PRIMARY KEY,
    supplier_id               VARCHAR NOT NULL,
    distribution_type           VARCHAR,          -- 'lognormal','gamma','weibull'
    shape_param                    NUMERIC(10,6),
    loc_param                         NUMERIC(10,6),
    scale_param                          NUMERIC(10,6),
    mean_lt_days                            NUMERIC(8,2),
    std_lt_days                                NUMERIC(8,2),
    p95_lt_days                                   NUMERIC(8,2),
    aic_score                                        NUMERIC(12,4),  -- goodness-of-fit, lower is better
    sample_size                                         INTEGER,

    model_version                                          VARCHAR,
    fitted_at                                                 TIMESTAMP DEFAULT now(),
    _batch_id                                                   VARCHAR
);

CREATE TABLE IF NOT EXISTS silver.demand_forecast (
    forecast_id           VARCHAR PRIMARY KEY,
    sku                   VARCHAR NOT NULL,
    location_id           VARCHAR NOT NULL,
    forecast_made_on      DATE NOT NULL,
    target_date           DATE NOT NULL,
    horizon_days          INTEGER,
    forecast_qty          NUMERIC(12,2),
    forecast_residual_std NUMERIC(12,2),   -- σ_D -- direct input to safety stock model
    model_version         VARCHAR NOT NULL,
    wmape_backtest        NUMERIC(6,4),
    bias_backtest         NUMERIC(6,4),
    _created_at           TIMESTAMP DEFAULT now(),
    _batch_id             VARCHAR
);

CREATE TABLE IF NOT EXISTS silver.late_delivery_risk_scores (
    score_id             VARCHAR PRIMARY KEY,
    order_line_id           VARCHAR NOT NULL REFERENCES silver_orders(order_line_id),
    predicted_prob_late        NUMERIC(6,5),   -- P(late), calibrated
    predicted_label               BOOLEAN,      -- thresholded prediction
    actual_label                     BOOLEAN,   -- ground truth, backfilled once order completes

    model_version                       VARCHAR NOT NULL,
    scored_at                              TIMESTAMP DEFAULT now(),
    _batch_id                                 VARCHAR
);

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

CREATE TABLE IF NOT EXISTS silver.dq_quarantine (
    quarantine_id       VARCHAR PRIMARY KEY,
    source_table           VARCHAR,          -- which silver table this record was destined for
    source_record_key         VARCHAR,
    failed_rule                  VARCHAR,       -- e.g. 'quantity_must_be_positive'
    raw_payload                     JSONB,       -- full offending row, for debugging
    quarantined_at                     TIMESTAMP DEFAULT now(),
    _batch_id                             VARCHAR
);