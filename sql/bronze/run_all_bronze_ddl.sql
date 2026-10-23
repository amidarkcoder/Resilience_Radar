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

CREATE TABLE IF NOT EXISTS bronze.products (
    sku                  VARCHAR,
    product_name         VARCHAR,
    category_name        VARCHAR,
    department_name      VARCHAR,
    unit_cost            NUMERIC(12,2),
    unit_weight_kg       NUMERIC(10,3),
    unit_price_msrp      NUMERIC(12,2),
    is_active            VARCHAR,          -- kept as VARCHAR ('Y'/'N'/'1'/'0') -- raw source inconsistency, normalized in silver
    catalog_snapshot_date DATE,

    _source_file          VARCHAR,
    _batch_id              VARCHAR,
    _ingested_at           TIMESTAMP DEFAULT now()
);

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
);-- Grain: one row per order LINE ITEM (order can have multiple lines/SKUs)
-- Source: synthetic generator mimicking DataCo Smart Supply Chain order structure

CREATE TABLE IF NOT EXISTS bronze.orders (
    order_id              VARCHAR,
    order_item_id         VARCHAR,          -- line-item level key
    order_date             TIMESTAMP,
    customer_id             VARCHAR,
    sku                      VARCHAR,
    order_item_quantity      INTEGER,
    order_item_unit_price    NUMERIC(12,2),
    order_item_discount_pct  NUMERIC(5,2),
    order_item_total         NUMERIC(14,2),

    order_status             VARCHAR,       -- 'COMPLETE','PENDING','CANCELED','ON_HOLD', etc. — raw, uncleaned casing
    shipping_mode             VARCHAR,       -- 'Standard Class','First Class','Second Class','Same Day'
    days_for_shipment_scheduled INTEGER,     -- promised transit days
    order_region               VARCHAR,
    order_country              VARCHAR,
    market                     VARCHAR,      -- 'LATAM','USCA','Europe','Africa','Pacific Asia'
    late_delivery_risk          VARCHAR,     -- raw source label, 0/1 as text — target for Model 3

    _source_file               VARCHAR,
    _batch_id                   VARCHAR,
    _ingested_at                TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bronze.order_lifecycle_events (
    event_id        VARCHAR,
    order_id        VARCHAR,
    event_type      VARCHAR,       -- 'PLACED','PICKED','PACKED','SHIPPED','DELIVERED','RETURNED'
    event_timestamp TIMESTAMP,
    event_location  VARCHAR,
    promised_date   DATE,          -- repeated on every event row in raw source (denormalized, as real systems do)

    _source_file     VARCHAR,
    _batch_id         VARCHAR,
    _ingested_at      TIMESTAMP DEFAULT now()
);


CREATE TABLE IF NOT EXISTS bronze.purchase_orders (
    po_id                   VARCHAR,
    po_line_id               VARCHAR,
    supplier_id                VARCHAR,
    sku                          VARCHAR,
    po_date                       DATE,
    promised_delivery_date         DATE,
    actual_delivery_date             DATE,   -- NULL if still in transit -- expected, handled in silver
    po_quantity                       INTEGER,
    unit_cost_at_po                    NUMERIC(12,2),
    incoterm                             VARCHAR,   -- 'FOB','CIF','DDP', etc.
    freight_mode                          VARCHAR,   -- 'Air','Ocean','Road','Rail'
    origin_country                         VARCHAR,
    destination_country                      VARCHAR,
    po_status                                 VARCHAR,  -- 'OPEN','CLOSED','PARTIALLY_RECEIVED','CANCELED'

    _source_file                              VARCHAR,
    _batch_id                                  VARCHAR,
    _ingested_at                                TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bronze.shipments (
    shipment_id         VARCHAR,
    order_id             VARCHAR,
    ship_date             TIMESTAMP,
    delivery_date           TIMESTAMP,
    origin_location           VARCHAR,
    destination_location        VARCHAR,
    shipping_mode                 VARCHAR,
    carrier_name                   VARCHAR,
    freight_cost                     NUMERIC(12,2),
    distance_km                        NUMERIC(10,2),
    transit_days_actual                  INTEGER,

    _source_file                         VARCHAR,
    _batch_id                             VARCHAR,
    _ingested_at                           TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bronze.inventory_snapshots (
    snapshot_date      DATE,
    sku                  VARCHAR,
    location_id            VARCHAR,
    location_type            VARCHAR,     -- 'DC','Plant','Store'
    on_hand_qty                INTEGER,
    on_order_qty                 INTEGER,
    backorder_qty                  INTEGER,
    safety_stock_target_qty          INTEGER,   -- as currently configured in WMS (pre-your-model baseline)

    _source_file                     VARCHAR,
    _batch_id                         VARCHAR,
    _ingested_at                       TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bronze.reference_tariffs (
    origin_country      VARCHAR,
    destination_country   VARCHAR,
    product_category        VARCHAR,
    tariff_rate_pct           NUMERIC(6,3),
    effective_date              DATE,
    expiry_date                   DATE,        -- NULL = currently in effect
    policy_note                    VARCHAR,

    _source_file                   VARCHAR,
    _batch_id                       VARCHAR,
    _ingested_at                     TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bronze.reference_fx_rates (
    rate_date          DATE,
    currency_from        VARCHAR(3),
    currency_to            VARCHAR(3),
    exchange_rate             NUMERIC(14,6),

    _source_file              VARCHAR,
    _batch_id                  VARCHAR,
    _ingested_at                TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bronze.reference_calendar (
    calendar_date      DATE,
    country               VARCHAR,       -- holidays are country-specific
    is_holiday              BOOLEAN,
    holiday_name              VARCHAR,
    is_weekend                  BOOLEAN,
    fiscal_year                   INTEGER,
    fiscal_period                   INTEGER,

    _source_file                    VARCHAR,
    _batch_id                        VARCHAR,
    _ingested_at                      TIMESTAMP DEFAULT now()
);