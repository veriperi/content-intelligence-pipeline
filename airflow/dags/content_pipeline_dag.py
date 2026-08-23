"""
Airflow DAG: Content Intelligence Pipeline

Schedule: daily
Flow:
    ingest_podcasts_and_episodes  (Bronze)
        -> enrich_with_llm         (Bronze, adds LLM output)
            -> dbt_run_silver       (Silver)
                -> dbt_run_gold      (Gold)

Each task is idempotent-ish by design: ingestion appends new bronze rows,
enrichment only processes episodes without existing enrichment rows, and
dbt models are full-refresh SELECTs recomputed from bronze/silver each run
— so re-running the DAG after a failure doesn't double-count anything
except bronze ingestion itself (which is intentionally append-only/raw).
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "content-pipeline",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

SEARCH_TERMS = ["technology", "true crime", "startup", "health", "comedy"]

with DAG(
    dag_id="content_intelligence_pipeline",
    description="Ingest podcast feeds, enrich with LLM, transform via dbt",
    default_args=default_args,
    schedule_interval="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["content", "genai", "dbt"],
) as dag:

    def _run_ingestion(**context):
        from app.ingest import run_full_ingestion
        result = run_full_ingestion(SEARCH_TERMS, podcasts_per_term=10)
        context["ti"].xcom_push(key="ingestion_summary", value=result)

    def _run_enrichment(**context):
        from app.llm_enrich import enrich_pending_episodes
        # Loop in batches until nothing pending, so a single run catches up
        # fully rather than leaving a backlog for tomorrow.
        total_processed = 0
        while True:
            result = enrich_pending_episodes(batch_size=50)
            total_processed += result["processed"]
            if result["processed"] == 0:
                break
        context["ti"].xcom_push(key="episodes_enriched", value=total_processed)

    ingest_task = PythonOperator(
        task_id="ingest_podcasts_and_episodes",
        python_callable=_run_ingestion,
    )

    enrich_task = PythonOperator(
        task_id="enrich_with_llm",
        python_callable=_run_enrichment,
    )

    dbt_silver = BashOperator(
        task_id="dbt_run_silver",
        bash_command="cd /opt/dbt/content_intelligence_pipeline && dbt run --select silver",
    )

    dbt_gold = BashOperator(
        task_id="dbt_run_gold",
        bash_command="cd /opt/dbt/content_intelligence_pipeline && dbt run --select gold",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command="cd /opt/dbt/content_intelligence_pipeline && dbt test",
    )

    ingest_task >> enrich_task >> dbt_silver >> dbt_gold >> dbt_test
