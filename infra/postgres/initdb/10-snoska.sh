#!/usr/bin/env bash
# Creates the databases and least-privilege roles used by the platform.
# snoska_owner owns the schema and runs migrations; snoska_app is the runtime
# role and is subject to row-level security (it never owns tenant tables).
set -euo pipefail

: "${SNOSKA_DB_OWNER_PASSWORD:?SNOSKA_DB_OWNER_PASSWORD is required}"
: "${SNOSKA_DB_APP_PASSWORD:?SNOSKA_DB_APP_PASSWORD is required}"
: "${KEYCLOAK_DB_PASSWORD:?KEYCLOAK_DB_PASSWORD is required}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
  -v owner_pw="$SNOSKA_DB_OWNER_PASSWORD" \
  -v app_pw="$SNOSKA_DB_APP_PASSWORD" \
  -v kc_pw="$KEYCLOAK_DB_PASSWORD" <<'SQL'
CREATE ROLE snoska_owner LOGIN PASSWORD :'owner_pw';
CREATE ROLE snoska_app LOGIN PASSWORD :'app_pw' NOBYPASSRLS;
CREATE ROLE keycloak LOGIN PASSWORD :'kc_pw';

CREATE DATABASE snoska OWNER snoska_owner;
CREATE DATABASE snoska_test OWNER snoska_owner;
CREATE DATABASE keycloak OWNER keycloak;
SQL

for db in snoska snoska_test; do
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$db" <<'SQL'
CREATE EXTENSION IF NOT EXISTS vector;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO snoska_owner;
GRANT USAGE ON SCHEMA public TO snoska_app;
SQL
done
