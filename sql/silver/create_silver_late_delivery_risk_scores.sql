

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