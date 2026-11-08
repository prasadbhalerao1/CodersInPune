"""DDL helpers for hand-written Alembic migrations.

Historical migrations import these, so changes here alter how old migrations
behave on a fresh database. Add new helpers rather than changing existing ones.
"""

import re

from alembic import context, op

_IDENT = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")

TENANT_POLICY = "tenant_isolation"


def _ident(name: str) -> str:
    if not _IDENT.fullmatch(name):
        raise ValueError(f"unsafe SQL identifier: {name!r}")
    return name


def app_role() -> str:
    """The restricted application role that migrations grant privileges to."""
    return _ident(str(context.config.attributes["app_db_role"]))


def qualified(schema: str, table: str) -> str:
    return f"{_ident(schema)}.{_ident(table)}"


def enable_tenant_rls(schema: str, table: str, column: str = "tenant_id") -> None:
    """Enable + force RLS with a fail-closed policy on `column`.

    FORCE makes the policy apply to the table owner too. The policy compares against
    `platform.current_tenant_id()`, which is NULL when no tenant is set, so the
    comparison is never true and no rows are visible or writable.
    """
    target = qualified(schema, table)
    col = _ident(column)
    op.execute(f"ALTER TABLE {target} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {target} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {TENANT_POLICY} ON {target} "
        f"USING ({col} = platform.current_tenant_id()) "
        f"WITH CHECK ({col} = platform.current_tenant_id())"
    )


def grant_table(schema: str, table: str, role: str, privileges: list[str]) -> None:
    allowed = {"SELECT", "INSERT", "UPDATE", "DELETE"}
    if not privileges or not set(privileges) <= allowed:
        raise ValueError(f"privileges must be a non-empty subset of {sorted(allowed)}")
    op.execute(f"GRANT {', '.join(privileges)} ON {qualified(schema, table)} TO {_ident(role)}")
