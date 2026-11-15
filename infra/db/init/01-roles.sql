-- Local development and CI only. Runs once as the bootstrap superuser when the
-- Postgres volume is first created (and explicitly in CI).
-- Production roles are provisioned on the hosting platform with secret passwords.
--
-- relay_owner: owns databases, schemas and tables; runs Alembic migrations.
-- relay_app:   used by the API and workers; no superuser, no BYPASSRLS, owns nothing.

CREATE ROLE relay_owner LOGIN PASSWORD 'relay_owner_dev'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE relay_app LOGIN PASSWORD 'relay_app_dev'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOINHERIT;

CREATE DATABASE relay OWNER relay_owner;
CREATE DATABASE relay_test OWNER relay_owner;

REVOKE ALL ON DATABASE relay FROM PUBLIC;
REVOKE ALL ON DATABASE relay_test FROM PUBLIC;
GRANT CONNECT ON DATABASE relay TO relay_app;
GRANT CONNECT ON DATABASE relay_test TO relay_app;
