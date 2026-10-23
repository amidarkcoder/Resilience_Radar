
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