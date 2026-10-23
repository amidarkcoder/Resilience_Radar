

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

CREATE TABLE IF NOT EXISTS gold.date (
    date_key            INTEGER PRIMARY KEY,     -- e.g. 20240315
    full_date              DATE NOT NULL UNIQUE,
    year_number               INTEGER,
    quarter_number                INTEGER,
    month_number                     INTEGER,
    month_name                          VARCHAR(10),
    week_of_year                           INTEGER,
    day_of_week                               INTEGER,     -- 1=Monday ... 7=Sunday
    day_name                                     VARCHAR(10),
    is_weekend                                      BOOLEAN,
    is_holiday                                         BOOLEAN,
    holiday_name                                          VARCHAR,
    fiscal_year                                              INTEGER,
    fiscal_period                                               INTEGER
);

CREATE TABLE IF NOT EXISTS gold.junk_order_flags (
    junk_key              BIGINT PRIMARY KEY,
    is_rush_order            BOOLEAN,
    is_return                   BOOLEAN,
    payment_type                   VARCHAR CHECK (payment_type IN ('Credit Card','Debit Card','PayPal','Wire','COD')),
    late_delivery_flag                 BOOLEAN,

    UNIQUE (is_rush_order, is_return, payment_type, late_delivery_flag)
);

CREATE TABLE IF NOT EXISTS gold.lane (
    lane_key              BIGINT PRIMARY KEY,
    origin_location_key      BIGINT REFERENCES location(location_key),
    dest_location_key           BIGINT REFERENCES location(location_key),
    shipping_mode                   VARCHAR,
    incoterm                           VARCHAR,
    typical_distance_km                   NUMERIC(10,2)
);

CREATE TABLE IF NOT EXISTS gold.location (
    location_key          BIGINT PRIMARY KEY,
    location_id              VARCHAR NOT NULL UNIQUE,
    location_name               VARCHAR,
    location_type                  VARCHAR CHECK (location_type IN ('Plant','DC','Store','Market')),
    city                              VARCHAR,
    country                              VARCHAR,
    latitude                               NUMERIC(9,6),
    longitude                                 NUMERIC(9,6)
);

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

CREATE INDEX idx_product_sku_current ON product (sku, is_current);

CREATE TABLE IF NOT EXISTS gold.scenario (
    scenario_key          BIGINT PRIMARY KEY,
    scenario_id              VARCHAR NOT NULL UNIQUE,
    parent_scenario_id          VARCHAR REFERENCES scenario(scenario_id),
    scenario_name                   VARCHAR,
    lever_type                         VARCHAR CHECK (lever_type IN
                                          ('none','buffer_stock','dual_source','nearshore')),
    params_json                            JSONB,         -- e.g. {"alt_supplier":"S-42","split_ratio":0.3}
    created_by                                VARCHAR,
    created_at                                   TIMESTAMP DEFAULT now()
);y

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

CREATE INDEX idx_supplier_id_current ON supplier (supplier_id, is_current);

CREATE TABLE IF NOT EXISTS gold.supplier_tier (
    bridge_key               BIGINT PRIMARY KEY,
    supplier_key                 BIGINT REFERENCES supplier(supplier_key),
    upstream_supplier_key           BIGINT REFERENCES supplier(supplier_key),
    tier_level                         INTEGER CHECK (tier_level >= 1),   -- 1 = direct, 2 = sub-supplier, etc.

    UNIQUE (supplier_key, upstream_supplier_key, tier_level)
);

CREATE TABLE IF NOT EXISTS gold.forecast (
    forecast_key            BIGINT PRIMARY KEY,
    product_key                BIGINT REFERENCES product(product_key),
    location_key                   BIGINT REFERENCES location(location_key),
    forecast_made_date_key             INTEGER REFERENCES date(date_key),
    target_date_key                       INTEGER REFERENCES date(date_key),
    horizon_days                             INTEGER,

    forecast_qty                                NUMERIC(12,2),
    forecast_residual_std                          NUMERIC(12,2),   -- σ_D, feeds safety stock model

    model_version                                     VARCHAR NOT NULL,
    wmape_backtest                                       NUMERIC(6,4),
    bias_backtest                                           NUMERIC(6,4),

    _loaded_at                                                 TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_fct_forecast_product_loc ON fct_forecast (product_key, location_key, model_version);


CREATE TABLE IF NOT EXISTS gold.inventory_position (
    product_key            BIGINT REFERENCES product(product_key),
    location_key               BIGINT REFERENCES location(location_key),
    date_key                       INTEGER REFERENCES date(date_key),

    on_hand_qty                       INTEGER,
    on_order_qty                         INTEGER,
    backorder_qty                           INTEGER,
    safety_stock_target_qty                    INTEGER,
    days_of_supply                                NUMERIC(8,2),

    PRIMARY KEY (product_key, location_key, date_key)
);

CREATE INDEX idx_fct_inventory_date ON fct_inventory_position (date_key);-- Grain: one row per ORDER (ACCUMULATING SNAPSHOT)


CREATE TABLE IF NOT EXISTS gold.order_lifecycle (
    order_id                     VARCHAR PRIMARY KEY,
    customer_key                    BIGINT REFERENCES customer(customer_key),

    placed_date_key                     INTEGER REFERENCES date(date_key),
    picked_date_key                        INTEGER REFERENCES date(date_key),
    packed_date_key                           INTEGER REFERENCES date(date_key),
    shipped_date_key                             INTEGER REFERENCES date(date_key),
    delivered_date_key                              INTEGER REFERENCES date(date_key),
    promised_date_key                                  INTEGER REFERENCES date(date_key),

    days_placed_to_picked                                 NUMERIC(6,2),
    days_picked_to_shipped                                   NUMERIC(6,2),
    days_shipped_to_delivered                                   NUMERIC(6,2),
    total_cycle_time_days                                          NUMERIC(6,2),

    ordered_qty                                                       INTEGER,
    delivered_qty                                                        INTEGER,
    is_on_time                                                              BOOLEAN,   -- delivered_date <= promised_date
    is_in_full                                                                 BOOLEAN,   -- delivered_qty >= ordered_qty
    otif_flag                                                                     BOOLEAN,   -- on_time AND in_full
    perfect_order_flag                                                               BOOLEAN,   -- OTIF + no damage/no return

    lifecycle_status                                                                    VARCHAR,   -- 'IN_PROGRESS','COMPLETE','RETURNED'
    _last_updated_at                                                                       TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gold.order_line (
    order_line_key        BIGINT PRIMARY KEY,
    order_id                 VARCHAR NOT NULL,
    date_key                    INTEGER REFERENCES date(date_key),
    product_key                    BIGINT REFERENCES product(product_key),
    customer_key                       BIGINT REFERENCES customer(customer_key),
    junk_key                               BIGINT REFERENCES junk_order_flags(junk_key),

    quantity                                  INTEGER,
    unit_price_usd                               NUMERIC(12,2),
    discount_pct                                    NUMERIC(5,2),
    line_total_usd                                     NUMERIC(14,2),

    _loaded_at                                            TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_fct_order_line_product ON fct_order_line (product_key);
CREATE INDEX idx_fct_order_line_date ON fct_order_line (date_key);

CREATE TABLE IF NOT EXISTS gold.scenario_plan (
    scenario_plan_key        BIGINT PRIMARY KEY,
    scenario_key                BIGINT REFERENCES scenario(scenario_key),
    product_key                    BIGINT REFERENCES product(product_key),
    location_key                       BIGINT REFERENCES location(location_key),

    metric_name                            VARCHAR CHECK (metric_name IN
                                              ('safety_stock_qty','reorder_point','expected_shortfall',
                                               'cvar_95','total_landed_cost_usd','service_level')),
    metric_value                                  NUMERIC(16,4),

    valid_from                                       DATE NOT NULL,
    valid_to                                            DATE NOT NULL DEFAULT '9999-12-31',
    recorded_at                                            TIMESTAMP DEFAULT now(),

    model_source                                              VARCHAR,   -- 'safety_stock_v1','dual_sourcing_mc_v2', etc.

    UNIQUE (scenario_key, product_key, location_key, metric_name, valid_from)
);

CREATE INDEX idx_fct_scenario_plan_scenario ON fct_scenario_plan (scenario_key);-- Grain: one row per outbound shipment (TRANSACTION fact)

CREATE TABLE IF NOT EXISTS gold.shipment (
    shipment_key           BIGINT PRIMARY KEY,
    order_id                  VARCHAR,
    lane_key                     BIGINT REFERENCES lane(lane_key),
    ship_date_key                   INTEGER REFERENCES date(date_key),
    delivery_date_key                   INTEGER REFERENCES date(date_key),

    carrier_name_std                       VARCHAR,
    freight_cost_usd                           NUMERIC(12,2),
    distance_km                                   NUMERIC(10,2),
    transit_days_actual                              INTEGER,

    _loaded_at                                          TIMESTAMP DEFAULT now()
);


CREATE TABLE IF NOT EXISTS gold.supplier_po (
    po_line_key            BIGINT PRIMARY KEY,
    po_id                      VARCHAR,
    supplier_key                  BIGINT REFERENCES supplier(supplier_key),
    product_key                      BIGINT REFERENCES product(product_key),
    po_date_key                         INTEGER REFERENCES date(date_key),

    promised_lead_time_days                INTEGER,
    actual_lead_time_days                     INTEGER,
    lead_time_variance_days                      INTEGER,
    is_po_open                                      BOOLEAN,

    po_quantity                                        INTEGER,
    unit_cost_usd                                         NUMERIC(12,2),
    incoterm                                                 VARCHAR,
    freight_mode                                                VARCHAR,

    _loaded_at                                                     TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_fct_supplier_po_supplier ON fct_supplier_po (supplier_key);

CREATE TABLE IF NOT EXISTS gold.cash_to_cash (
    year_month               VARCHAR(7) PRIMARY KEY,

    days_inventory_outstanding   NUMERIC(8,2),   -- DIO: avg inventory value / COGS per day
    days_sales_outstanding          NUMERIC(8,2),   -- DSO: avg receivables / revenue per day
    days_payable_outstanding           NUMERIC(8,2),   -- DPO: avg payables / COGS per day
    cash_to_cash_days                     NUMERIC(8,2),   -- DIO + DSO - DPO

    _computed_at                             TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gold.otif (
    product_key             BIGINT REFERENCES product(product_key),
    location_key                BIGINT REFERENCES location(location_key),
    year_month                     VARCHAR(7),      -- 'YYYY-MM'

    total_orders                      INTEGER,
    on_time_orders                       INTEGER,
    in_full_orders                          INTEGER,
    otif_orders                                INTEGER,
    otif_pct                                      NUMERIC(6,4),

    avg_cycle_time_days                               NUMERIC(6,2),

    _computed_at                                         TIMESTAMP DEFAULT now(),

    PRIMARY KEY (product_key, location_key, year_month)
);

CREATE TABLE IF NOT EXISTS gold.perfect_order (
    product_key             BIGINT REFERENCES product(product_key),
    location_key                BIGINT REFERENCES location(location_key),
    year_month                     VARCHAR(7),

    total_orders                      INTEGER,
    perfect_orders                       INTEGER,
    perfect_order_pct                       NUMERIC(6,4),

    return_rate_pct                            NUMERIC(6,4),
    damage_rate_pct                               NUMERIC(6,4),

    _computed_at                                     TIMESTAMP DEFAULT now(),

    PRIMARY KEY (product_key, location_key, year_month)
);