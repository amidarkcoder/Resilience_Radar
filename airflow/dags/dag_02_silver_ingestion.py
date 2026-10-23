from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from src.silver.load_silver import run

default_args = {
    "owner": "resilience_radar",
    "retries": 0,
}

with DAG(
    dag_id="silver_processing",
    description="Stage 2: clean bronze data, apply ML/statistical models, write to silver schema",
    default_args=default_args,
    schedule=None,          # trigger manually for now, same as bronze_ingestion
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["silver", "resilience_radar"],
) as dag:

    run_silver_pipeline = PythonOperator(
        task_id="run_silver_pipeline",
        python_callable=run,
        op_kwargs={
            "conn_str": "{{ var.value.get('warehouse_conn_string', "
                        "'postgresql+psycopg2://warehouse_admin:CHANGEME@postgres_warehouse:5432/resilience_radar') }}",
        },
    )