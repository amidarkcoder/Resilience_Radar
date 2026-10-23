
CREATE TABLE IF NOT EXISTS gold.date (
    date_key            INTEGER PRIMARY KEY,     -- e.g. 20240315
    full_date              DATE NOT NULL UNIQUE,
    year_number               INTEGER,
    quarter_number                INTEGER,
    month_number                     INTEGER,
    month_name                          VARCHAR(10),
    week_of_year                           INTEGER,
    day_of_week                               INTEGER,     -- 1=Monday ... 7=Sunday
    day_name                                     VARCHAR(10),
    is_weekend                                      BOOLEAN,
    is_holiday                                         BOOLEAN,
    holiday_name                                          VARCHAR,
    fiscal_year                                              INTEGER,
    fiscal_period                                               INTEGER
);