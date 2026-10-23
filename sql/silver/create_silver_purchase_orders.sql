
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