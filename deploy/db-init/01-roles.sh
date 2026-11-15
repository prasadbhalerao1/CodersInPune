#!/bin/sh
# Production role provisioning for the bundled Postgres container. Runs once, when the
# data volume is first created. Passwords come from the environment, never from files.
#
# relay_owner: owns the database and schemas; runs migrations.
# relay_app:   used by the API and worker; no superuser, no BYPASSRLS, owns nothing.
# For a managed database, run the equivalent SQL once as an administrator instead.
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
  -v owner_pw="$RELAY_OWNER_DB_PASSWORD" -v app_pw="$RELAY_APP_DB_PASSWORD" <<'SQL'
CREATE ROLE relay_owner LOGIN PASSWORD :'owner_pw'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE relay_app LOGIN PASSWORD :'app_pw'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOINHERIT;
CREATE DATABASE relay OWNER relay_owner;
REVOKE ALL ON DATABASE relay FROM PUBLIC;
GRANT CONNECT ON DATABASE relay TO relay_app;
SQL
