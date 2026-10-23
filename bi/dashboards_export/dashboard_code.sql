--TOTAL ORDER
SELECT COUNT(*) AS total_order_lines FROM gold.fact_order_lines;
--TOTAL NUMBER OF PURCHASE ORDERS
SELECT COUNT(*) AS total_purchase_orders FROM gold.fact_purchase_orders;

--OTIF PERCENTAGE
SELECT ROUND(AVG(otif_pct)::numeric, 1) AS otif_pct
FROM gold.otif_mart
WHERE year_month = (SELECT MAX(year_month) FROM gold.otif_mart);

--SKUS RECOMMENDED SWITCH
SELECT COUNT(*) AS skus_recommended_switch
FROM gold.nearshoring_milp
WHERE current_supplier_id  IS DISTINCT FROM recommended_supplier_id  ;

--MEAN FORECAST ERROR
SELECT ROUND(AVG(ABS(model_mae  - predicted_next_week_qty))::numeric, 1) AS mean_abs_forecast_error
FROM gold.fact_demand_forecast;
--TOTAL SAFETY STOCK UNITS
SELECT SUM(safety_stock_units) AS total_safety_stock_units
FROM gold.safety_stock;

--FORECAST VS ACTUAL    
SELECT forecast_week  AS time,
       SUM(model_mae ) AS actual,
       SUM(predicted_next_week_qty) AS forecast
FROM gold.fact_demand_forecast
GROUP BY 1 ORDER BY 1;

--OTIF PERCENTAGE BY MONTH
SELECT year_month AS time, ROUND(AVG(otif_pct)::numeric, 2) AS otif_pct
FROM gold.otif_mart
GROUP BY 1 ORDER BY 1;

--SAFETY STOCK PER PRODUCT
SELECT sku, safety_stock_units
FROM gold.safety_stock
ORDER BY safety_stock_units DESC
LIMIT 10;

--OTIF IMPACT BY SUPPILER
SELECT supplier_tier, ROUND(AVG(otif_pct)::numeric, 1) AS otif_pct
FROM gold.otif_mart
GROUP BY 1
ORDER BY 2 DESC;