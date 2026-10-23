
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