
CREATE TABLE IF NOT EXISTS silver.dq_quarantine (
    quarantine_id       VARCHAR PRIMARY KEY,
    source_table           VARCHAR,          -- which silver table this record was destined for
    source_record_key         VARCHAR,
    failed_rule                  VARCHAR,       -- e.g. 'quantity_must_be_positive'
    raw_payload                     JSONB,       -- full offending row, for debugging
    quarantined_at                     TIMESTAMP DEFAULT now(),
    _batch_id                             VARCHAR
);