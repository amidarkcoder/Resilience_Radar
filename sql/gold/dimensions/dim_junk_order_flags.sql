
CREATE TABLE IF NOT EXISTS gold.junk_order_flags (
    junk_key              BIGINT PRIMARY KEY,
    is_rush_order            BOOLEAN,
    is_return                   BOOLEAN,
    payment_type                   VARCHAR CHECK (payment_type IN ('Credit Card','Debit Card','PayPal','Wire','COD')),
    late_delivery_flag                 BOOLEAN,

    UNIQUE (is_rush_order, is_return, payment_type, late_delivery_flag)
);