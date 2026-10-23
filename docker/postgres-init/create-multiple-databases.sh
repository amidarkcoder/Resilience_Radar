#!/bin/bash
set -e
set -u

function create_user_and_database() {
    local database=$1
    local user=$2
    local password=$3
    echo "Creating user '$user' and database '$database'"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
        CREATE USER $user WITH PASSWORD '$password';
        CREATE DATABASE $database OWNER $user;
        GRANT ALL PRIVILEGES ON DATABASE $database TO $user;
EOSQL
}

create_user_and_database "$SUPERSET_DB_NAME" "$SUPERSET_DB_USER" "$SUPERSET_DB_PASSWORD"
