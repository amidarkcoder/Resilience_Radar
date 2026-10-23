
CREATE SCHEMA IF NOT EXISTS bronze;

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