
CREATE TABLE IF NOT EXISTS gold.scenario (
    scenario_key          BIGINT PRIMARY KEY,
    scenario_id              VARCHAR NOT NULL UNIQUE,
    parent_scenario_id          VARCHAR REFERENCES scenario(scenario_id),
    scenario_name                   VARCHAR,
    lever_type                         VARCHAR CHECK (lever_type IN
                                          ('none','buffer_stock','dual_source','nearshore')),
    params_json                            JSONB,         -- e.g. {"alt_supplier":"S-42","split_ratio":0.3}
    created_by                                VARCHAR,
    created_at                                   TIMESTAMP DEFAULT now()
);