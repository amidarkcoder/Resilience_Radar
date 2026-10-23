
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

CREATE INDEX idx_fct_scenario_plan_scenario ON fct_scenario_plan (scenario_key);