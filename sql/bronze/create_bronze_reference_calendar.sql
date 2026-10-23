
CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.reference_calendar (
    calendar_date      DATE,
    country               VARCHAR,       -- holidays are country-specific
    is_holiday              BOOLEAN,
    holiday_name              VARCHAR,
    is_weekend                  BOOLEAN,
    fiscal_year                   INTEGER,
    fiscal_period                   INTEGER,

    _source_file                    VARCHAR,
    _batch_id                        VARCHAR,
    _ingested_at                      TIMESTAMP DEFAULT now()
);