"""platform schema, tenant context function and tenant table

Revision ID: 0001
Revises:
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from relay.shared.db.migration_ops import app_role, enable_tenant_rls, grant_table

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    role = app_role()
    op.execute("CREATE SCHEMA platform")
    op.execute(f"GRANT USAGE ON SCHEMA platform TO {role}")

    # NULL when unset or set to '' (a custom setting keeps '' after SET LOCAL ends),
    # so RLS comparisons fail closed. Invalid values raise rather than match.
    op.execute(
        """
        CREATE FUNCTION platform.current_tenant_id() RETURNS uuid
        LANGUAGE sql STABLE PARALLEL SAFE
        AS $$ SELECT NULLIF(pg_catalog.current_setting('app.tenant_id', true), '')::uuid $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION platform.current_tenant_id() FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION platform.current_tenant_id() TO {role}")

    op.create_table(
        "tenant",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tenant"),
        schema="platform",
    )
    # A tenant row is visible only inside its own context.
    enable_tenant_rls("platform", "tenant", column="id")
    grant_table("platform", "tenant", role, ["SELECT", "INSERT", "UPDATE"])


def downgrade() -> None:
    op.drop_table("tenant", schema="platform")
    op.execute("DROP FUNCTION platform.current_tenant_id()")
    op.execute("DROP SCHEMA platform")
