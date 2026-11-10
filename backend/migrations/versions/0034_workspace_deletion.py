"""workspace deletion with a grace period

- platform.tenant.deletion_requested_at/_by: the owner scheduled deletion. The workspace
  keeps working (so data can be exported) and the request can be cancelled until the
  grace period ends.
- platform.tenant_deletion_due(id): true once the grace period (30 days) has passed.
- The purge runs as the owner role (`relay-purge-workspaces`), never as relay_app. The
  owner may discover due workspaces (`purge_due` policy) and nothing else across tenants.
- The append-only triggers on audit events and ownership history still refuse every
  change, except deleting the rows of a workspace whose deletion is due. relay_app has no
  DELETE grant on either table, so the application can never use that exception.
- identity.workspace_creation_request rows go with their workspace (ON DELETE CASCADE);
  they are per-user rows the tenant context can't see.

Revision ID: 0034
Revises: 0033
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FK = "fk_workspace_creation_request_created_tenant_id_tenant"
TRIGGERS = (
    ("audit", "audit events are append-only"),
    ("catalog", "ownership change history is append-only"),
)


def _reject_change(schema: str, message: str, allow_purge: bool) -> None:
    purge = (
        "IF TG_OP = 'DELETE' AND platform.tenant_deletion_due(OLD.tenant_id) THEN "
        "RETURN OLD; END IF;"
        if allow_purge
        else ""
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {schema}.reject_change() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            {purge}
            RAISE EXCEPTION '{message}' USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )


def _creation_request_fk(ondelete: str | None) -> None:
    op.drop_constraint(FK, "workspace_creation_request", schema="identity", type_="foreignkey")
    op.create_foreign_key(
        FK,
        "workspace_creation_request",
        "tenant",
        ["created_tenant_id"],
        ["id"],
        source_schema="identity",
        referent_schema="platform",
        ondelete=ondelete,
        deferrable=True,
        initially="DEFERRED",
    )


def upgrade() -> None:
    op.add_column(
        "tenant",
        sa.Column("deletion_requested_at", sa.DateTime(timezone=True), nullable=True),
        schema="platform",
    )
    op.add_column(
        "tenant", sa.Column("deletion_requested_by", sa.Uuid(), nullable=True), schema="platform"
    )
    op.execute(
        """
        CREATE FUNCTION platform.tenant_deletion_due(tid uuid) RETURNS boolean
        LANGUAGE sql STABLE AS $$
          SELECT EXISTS (
            SELECT 1 FROM platform.tenant t
            WHERE t.id = tid AND t.deletion_requested_at <= now() - interval '30 days')
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION platform.tenant_deletion_due(uuid) FROM PUBLIC")
    op.execute(
        "CREATE POLICY purge_due ON platform.tenant FOR SELECT TO CURRENT_USER "
        "USING (deletion_requested_at <= now() - interval '30 days')"
    )
    for schema, message in TRIGGERS:
        _reject_change(schema, message, allow_purge=True)
    _creation_request_fk("CASCADE")


def downgrade() -> None:
    _creation_request_fk(None)
    for schema, message in TRIGGERS:
        _reject_change(schema, message, allow_purge=False)
    op.execute("DROP POLICY purge_due ON platform.tenant")
    op.execute("DROP FUNCTION platform.tenant_deletion_due(uuid)")
    op.drop_column("tenant", "deletion_requested_by", schema="platform")
    op.drop_column("tenant", "deletion_requested_at", schema="platform")
