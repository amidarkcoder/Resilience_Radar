
from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from src.gold.load_gold import run


default_args = {"owner": "resilience_radar", "retries": 0}

with DAG(
    dag_id="gold_business_marts",
    description="Stage 3: build dimensions, facts, KPI marts, and models in gold schema",
    default_args=default_args,
    schedule=None,
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["gold", "resilience_radar"],
) as dag:
    run_gold_pipeline = PythonOperator(
        task_id="run_gold_pipeline",
        python_callable=run,
        op_kwargs={
            "conn_str": "{{ var.value.get('warehouse_conn_string', "
                        "'postgresql+psycopg2://warehouse_admin:CHANGEME@postgres_warehouse:5432/resilience_radar') }}",
        },
    )

