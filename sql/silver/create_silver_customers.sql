
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