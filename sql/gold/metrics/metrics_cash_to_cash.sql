
CREATE TABLE IF NOT EXISTS gold.cash_to_cash (
    year_month               VARCHAR(7) PRIMARY KEY,

    days_inventory_outstanding   NUMERIC(8,2),   -- DIO: avg inventory value / COGS per day
    days_sales_outstanding          NUMERIC(8,2),   -- DSO: avg receivables / revenue per day
    days_payable_outstanding           NUMERIC(8,2),   -- DPO: avg payables / COGS per day
    cash_to_cash_days                     NUMERIC(8,2),   -- DIO + DSO - DPO

    _computed_at                             TIMESTAMP DEFAULT now()
);