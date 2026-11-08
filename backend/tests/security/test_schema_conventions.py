"""Catalog checks that keep every future tenant table on the isolation conventions.

Runs against the migrated test database, so a new migration that forgets RLS,
a tenant-prefixed unique key or a composite foreign key fails CI.
"""

from collections.abc import Iterator

import psycopg
import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

# Register every model on Base.metadata for the drift check.
import relay.audit.models
import relay.catalog.models
import relay.continuity.models
import relay.directory.models
import relay.identity.models
import relay.integrations.github.models
import relay.jobs.models
import relay.notifications.models
import relay.platform.models
import relay.risks.models  # noqa: F401
from relay.shared.db.base import Base
from tests.db import APP_ROLE, OWNER_URL, libpq_url

MANAGED_SCHEMAS = (
    "platform",
    "identity",
    "audit",
    "directory",
    "catalog",
    "continuity",
    "integrations",
    "risks",
    "notifications",
)
TENANT_ROOT = ("platform", "tenant")
# Global (not tenant-scoped) tables. Each must still force RLS with explicit policies.
GLOBAL_TABLES = {("identity", "user_account"), ("identity", "workspace_creation_request")}


@pytest.fixture
def catalog() -> Iterator[psycopg.Connection]:
    with psycopg.connect(libpq_url(OWNER_URL)) as conn:
        yield conn


def tenant_tables(conn: psycopg.Connection) -> list[tuple[str, str]]:
    rows = conn.execute(
        """
        SELECT table_schema, table_name FROM information_schema.columns
        WHERE column_name = 'tenant_id' AND table_schema = ANY(%s)
        ORDER BY 1, 2
        """,
        (list(MANAGED_SCHEMAS),),
    ).fetchall()
    return [(r[0], r[1]) for r in rows]


def test_every_managed_table_is_tenant_scoped_or_the_tenant_root(
    catalog: psycopg.Connection,
) -> None:
    rows = catalog.execute(
        "SELECT schemaname, tablename FROM pg_tables WHERE schemaname = ANY(%s)",
        (list(MANAGED_SCHEMAS),),
    ).fetchall()
    scoped = set(tenant_tables(catalog))
    unscoped = {(r[0], r[1]) for r in rows} - scoped - {TENANT_ROOT} - GLOBAL_TABLES
    assert unscoped == set(), "tables without tenant_id need an explicit exemption"


def test_global_tables_force_rls_with_policies(catalog: psycopg.Connection) -> None:
    for schema, table in sorted(GLOBAL_TABLES):
        row = catalog.execute(
            """
            SELECT c.relrowsecurity, c.relforcerowsecurity,
                   (SELECT count(*) FROM pg_policy p WHERE p.polrelid = c.oid) > 0
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s AND c.relname = %s
            """,
            (schema, table),
        ).fetchone()
        assert row == (True, True, True), f"{schema}.{table}"


def test_rls_enabled_forced_and_policy_present(catalog: psycopg.Connection) -> None:
    for schema, table in [*tenant_tables(catalog), TENANT_ROOT]:
        enabled, forced, policies = catalog.execute(
            """
            SELECT c.relrowsecurity, c.relforcerowsecurity,
                   (SELECT count(*) FROM pg_policy p
                    WHERE p.polrelid = c.oid AND p.polname = 'tenant_isolation')
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s AND c.relname = %s
            """,
            (schema, table),
        ).fetchone() or (False, False, 0)
        assert (enabled, forced, policies) == (True, True, 1), f"{schema}.{table}"


def test_unique_keys_are_tenant_prefixed(catalog: psycopg.Connection) -> None:
    for schema, table in tenant_tables(catalog):
        indexes = catalog.execute(
            """
            SELECT i.indexrelid::regclass::text,
                   (SELECT a.attname FROM pg_attribute a
                    WHERE a.attrelid = i.indrelid AND a.attnum = i.indkey[0])
            FROM pg_index i
            WHERE i.indrelid = %s::regclass AND i.indisunique AND NOT i.indisprimary
            """,
            (f"{schema}.{table}",),
        ).fetchall()
        for index_name, first_column in indexes:
            assert first_column == "tenant_id", f"{index_name} must start with tenant_id"
        has_tenant_id_key = catalog.execute(
            """
            SELECT 1 FROM pg_constraint
            WHERE conrelid = %s::regclass AND contype = 'u'
              AND conkey = ARRAY[
                (SELECT attnum FROM pg_attribute WHERE attrelid = %s::regclass
                 AND attname = 'tenant_id'),
                (SELECT attnum FROM pg_attribute WHERE attrelid = %s::regclass
                 AND attname = 'id')]::int2[]
            """,
            (f"{schema}.{table}",) * 3,
        ).fetchone()
        assert has_tenant_id_key, f"{schema}.{table} needs UNIQUE (tenant_id, id)"


def test_references_to_tenant_tables_include_tenant_id(catalog: psycopg.Connection) -> None:
    scoped = {f"{s}.{t}" for s, t in tenant_tables(catalog)}
    fks = catalog.execute(
        """
        SELECT c.conname, c.conrelid::regclass::text, c.confrelid::regclass::text,
               ARRAY(SELECT a.attname FROM unnest(c.conkey) k
                     JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k)
        FROM pg_constraint c
        WHERE c.contype = 'f' AND c.connamespace = ANY(
            SELECT oid FROM pg_namespace WHERE nspname = ANY(%s))
        """,
        (list(MANAGED_SCHEMAS),),
    ).fetchall()
    for name, source, target, columns in fks:
        if source in scoped and target in scoped:
            assert "tenant_id" in columns, f"{name} must be a composite (tenant_id, ...) key"


def test_application_role_owns_nothing_and_cannot_bypass_rls(
    catalog: psycopg.Connection,
) -> None:
    row = catalog.execute(
        "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = %s", (APP_ROLE,)
    ).fetchone()
    assert row == (False, False)
    owned = catalog.execute(
        "SELECT count(*) FROM pg_class c JOIN pg_roles r ON r.oid = c.relowner "
        "WHERE r.rolname = %s",
        (APP_ROLE,),
    ).fetchone()
    assert owned == (0,)


def test_models_match_migrations() -> None:
    def include_name(name: str | None, type_: str, _parent: object) -> bool:
        return name in MANAGED_SCHEMAS if type_ == "schema" else True

    engine = create_engine(OWNER_URL)
    try:
        with engine.connect() as conn:
            context = MigrationContext.configure(
                conn, opts={"include_schemas": True, "include_name": include_name}
            )
            assert compare_metadata(context, Base.metadata) == []
    finally:
        engine.dispose()


def test_check_constraint_names_are_not_double_prefixed(catalog: psycopg.Connection) -> None:
    doubled = catalog.execute(
        "SELECT conname FROM pg_constraint WHERE contype = 'c' AND conname ~ '^ck_.*_ck_'"
    ).fetchall()
    assert doubled == [], "use op.f('ck_...') for explicit CHECK names in migrations"
