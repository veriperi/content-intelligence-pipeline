# Airflow, extended with our own pipeline code and dbt, so the DAG's
# PythonOperator and BashOperator tasks can actually import our modules
# and run dbt commands without any extra setup.
FROM apache/airflow:2.9.3-python3.11

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER airflow

# Install our backend's Python dependencies (ingestion, LLM enrichment)
# plus dbt, constrained against Airflow's own official constraints file.
# This is Airflow's officially recommended pattern for adding extra
# packages: it prevents pip from silently upgrading a dependency (like
# SQLAlchemy) to a version that breaks Airflow's own internals.
ARG AIRFLOW_VERSION=2.9.3
ARG PYTHON_VERSION=3.11
ARG CONSTRAINT_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"

COPY airflow/requirements.txt /tmp/airflow-requirements.txt
RUN pip install --no-cache-dir -r /tmp/airflow-requirements.txt --constraint "${CONSTRAINT_URL}"

RUN pip install --no-cache-dir dbt-core==1.8.0 dbt-postgres==1.8.0 --constraint "${CONSTRAINT_URL}"

# Copy our actual application code so `from app.ingest import ...` works
# inside the DAG's PythonOperator tasks.
COPY backend/app /opt/airflow/app
ENV PYTHONPATH=/opt/airflow

# Copy the dbt project to the path the DAG's BashOperator tasks expect.
# --chown ensures the 'airflow' user actually owns these files, since a
# plain COPY defaults to root ownership, which then blocks dbt from
# writing its own log file at runtime (dbt.log, target/, etc).
COPY --chown=airflow:0 dbt /opt/dbt/content_intelligence_pipeline

# Custom startup script: runs Airflow against Postgres instead of the
# default SQLite used by 'airflow standalone', to avoid SQLite's
# "database is locked" errors under concurrent access.
COPY --chown=airflow:0 airflow/entrypoint.sh /entrypoint.sh
USER root
RUN chmod +x /entrypoint.sh
USER airflow