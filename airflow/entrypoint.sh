#!/bin/bash
# Initializes Airflow's own metadata database (in Postgres, not SQLite) and
# starts the webserver + scheduler. Using Postgres here — instead of the
# 'airflow standalone' shortcut's built-in SQLite — avoids SQLite's
# well-known "database is locked" errors under concurrent access from
# multiple Airflow processes writing at once.
set -e

echo "Running Airflow DB migrations..."
airflow db migrate

echo "Ensuring admin user exists..."
airflow users create \
    --username admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com \
    --password admin || true

echo "Starting webserver in the background..."
airflow webserver --port 8080 &

echo "Starting scheduler in the foreground..."
exec airflow scheduler
