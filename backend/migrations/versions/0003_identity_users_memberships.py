"""identity schema: users, workspace memberships, workspace creation idempotency

Principal context: `app.principal` holds the verified WorkOS user ID of the caller,
set per transaction like `app.tenant_id`.

Policies (all fail closed when the setting is empty):
- user_account: a principal sees and writes only its own row.
- membership: standard tenant isolation, plus SELECT of the caller's own memberships in
  any workspace (needed to resolve which workspaces the caller may enter).
- workspace_creation_request: the caller's own idempotency records only.
- platform.tenant: additionally readable when the caller has an active membership.

Policy dependencies are one-directional (tenant -> membership -> user_account), so no
policy recursion is possible.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from relay.shared.db.migration_ops import (
    app_role,
    enable_rls,
    enable_tenant_rls,
    grant_function,
    grant_table,
)

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLES = "('owner', 'admin', 'member', 'guest', 'auditor')"
STATUSES = "('active', 'suspended', 'removed')"
CURRENT_USER = "(SELECT identity.current_user_id())"


def _timestamps() -> list[sa.Column[sa.DateTime]]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    role = app_role()
    op.execute("CREATE SCHEMA identity")
    op.execute(f"GRANT USAGE ON SCHEMA identity TO {role}")

    op.execute(
        """
        CREATE FUNCTION identity.current_principal() RETURNS text
        LANGUAGE sql STABLE PARALLEL SAFE
        AS $$ SELECT NULLIF(pg_catalog.current_setting('app.principal', true), '') $$
        """
    )
    grant_function("identity.current_principal()", role)

    op.create_table(
        "user_account",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("workos_user_id", sa.Text(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_user_account"),
        sa.UniqueConstraint("workos_user_id", name="uq_user_account_workos_user_id"),
        sa.CheckConstraint(
            "char_length(workos_user_id) BETWEEN 1 AND 255",
            name="ck_user_account_workos_user_id_length",
        ),
        schema="identity",
    )
    enable_rls("identity", "user_account")
    op.execute(
        "CREATE POLICY principal_self ON identity.user_account "
        "USING (workos_user_id = identity.current_principal()) "
        "WITH CHECK (workos_user_id = identity.current_principal())"
    )
    grant_table("identity", "user_account", role, ["SELECT", "INSERT", "UPDATE"])

    # Relies on principal_self: the caller can only ever resolve their own id.
    op.execute(
        """
        CREATE FUNCTION identity.current_user_id() RETURNS uuid
        LANGUAGE sql STABLE PARALLEL SAFE
        AS $$ SELECT id FROM identity.user_account
              WHERE workos_user_id = identity.current_principal() $$
        """
    )
    grant_function("identity.current_user_id()", role)

    op.create_table(
        "membership",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_membership"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["platform.tenant.id"], name="fk_membership_tenant_id_tenant"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["identity.user_account.id"], name="fk_membership_user_id_user_account"
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_membership_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_membership_tenant_id_user_id"),
        sa.CheckConstraint(f"role IN {ROLES}", name="ck_membership_role"),
        sa.CheckConstraint(f"status IN {STATUSES}", name="ck_membership_status"),
        schema="identity",
    )
    op.create_index("ix_membership_user_id", "membership", ["user_id"], schema="identity")
    enable_tenant_rls("identity", "membership")
    op.execute(
        "CREATE POLICY member_self_read ON identity.membership FOR SELECT "
        f"USING (user_id = {CURRENT_USER})"
    )
    grant_table("identity", "membership", role, ["SELECT", "INSERT", "UPDATE"])

    op.create_table(
        "workspace_creation_request",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("created_tenant_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("user_id", "idempotency_key", name="pk_workspace_creation_request"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["identity.user_account.id"],
            name="fk_workspace_creation_request_user_id_user_account",
        ),
        sa.ForeignKeyConstraint(
            ["created_tenant_id"],
            ["platform.tenant.id"],
            name="fk_workspace_creation_request_created_tenant_id_tenant",
            deferrable=True,
            initially="DEFERRED",
        ),
        schema="identity",
    )
    enable_rls("identity", "workspace_creation_request")
    op.execute(
        "CREATE POLICY requester_self ON identity.workspace_creation_request "
        f"USING (user_id = {CURRENT_USER}) WITH CHECK (user_id = {CURRENT_USER})"
    )
    grant_table("identity", "workspace_creation_request", role, ["SELECT", "INSERT"])

    op.execute(
        "CREATE POLICY member_workspaces_read ON platform.tenant FOR SELECT USING ("
        "id IN (SELECT m.tenant_id FROM identity.membership m "
        f"WHERE m.user_id = {CURRENT_USER} AND m.status = 'active'))"
    )


def downgrade() -> None:
    op.execute("DROP POLICY member_workspaces_read ON platform.tenant")
    op.drop_table("workspace_creation_request", schema="identity")
    op.drop_table("membership", schema="identity")
    op.execute("DROP FUNCTION identity.current_user_id()")
    op.drop_table("user_account", schema="identity")
    op.execute("DROP FUNCTION identity.current_principal()")
    op.execute("DROP SCHEMA identity")
