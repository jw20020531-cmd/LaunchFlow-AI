#!/bin/sh
set -eu
psql --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<'SQL'
\getenv app_password LAUNCHFLOW_DB_PASSWORD
CREATE ROLE launchflow LOGIN PASSWORD :'app_password' NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE DATABASE launchflow OWNER launchflow;
REVOKE CONNECT ON DATABASE launchflow FROM PUBLIC;
SQL
