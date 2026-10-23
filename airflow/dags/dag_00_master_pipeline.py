
from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator

from src.bronze.load_bronze import run as run_bronze
from src.silver.load_silver import run as run_silver
from src.gold.load_gold import run as run_gold

default_args = {"owner": "resilience_radar", "retries": 0}

CONN_STR_TEMPLATE = (
    "{{ var.value.get('warehouse_conn_string', "
    "'postgresql+psycopg2://warehouse_admin:CHANGEME@postgres_warehouse:5432/resilience_radar') }}"
)

with DAG(
    dag_id="master_pipeline",
    description="End-to-end: generate bronze data -> clean/model silver -> build gold marts",
    default_args=default_args,
    schedule=None,
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["master", "bronze", "silver", "gold", "resilience_radar"],
) as dag:

    bronze_task = PythonOperator(
        task_id="generate_and_load_bronze_data",
        python_callable=run_bronze,
        op_kwargs={"conn_str": CONN_STR_TEMPLATE},
    )

    silver_task = PythonOperator(
        task_id="run_silver_pipeline",
        python_callable=run_silver,
        op_kwargs={"conn_str": CONN_STR_TEMPLATE},
    )

    gold_task = PythonOperator(
        task_id="run_gold_pipeline",
        python_callable=run_gold,
        op_kwargs={"conn_str": CONN_STR_TEMPLATE},
    )

    bronze_task >> silver_task >> gold_task