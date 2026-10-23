FROM apache/superset:3.1.0

USER root

# psycopg2 driver so Superset can connect to the Postgres warehouse (gold schema)
RUN pip install --no-cache-dir psycopg2-binary

USER superset