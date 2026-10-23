from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from src.bronze.load_bronze import run

default_args = {
    "owner": "resilience_radar",
    "retries": 0,
}

with DAG(
    dag_id="bronze_ingestion",
    description="Stage 1: generate synthetic data and load into bronze schema",
    default_args=default_args,
    schedule=None,          # trigger manually for now
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["bronze", "resilience_radar"],
) as dag:

    generate_and_load_bronze_data = PythonOperator(
        task_id="generate_and_load_bronze_data",
        python_callable=run,
        op_kwargs={
            "conn_str": "{{ var.value.get('warehouse_conn_string', "
                        "'postgresql+psycopg2://warehouse_admin:CHANGEME@postgres_warehouse:5432/resilience_radar') }}",
        },
    )