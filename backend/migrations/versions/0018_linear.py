"""Linear integration (read-only): connection, teams, projects, people, issue metadata

- linear_connection: one Linear workspace per Relay workspace connection. The OAuth
  access token is stored encrypted (Fernet, server-side key); it is never returned by
  the API. Scope requested: read.
- linear_team / linear_project: optionally linked to a Relay team / responsibility.
- linear_identity: Linear users; linked to a person only by explicit decision (unique
  per person), exactly like GitHub identities.
- linear_issue: metadata only (identifier, title, state, priority, people, labels,
  timestamps, relationships). No descriptions or comments.

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

from relay.shared.db.migration_ops import app_role, enable_tenant_rls, grant_table

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

S = "integrations"


def _base(table: str) -> list[sa.SchemaItem]:
    return [
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=f"pk_{table}"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["platform.tenant.id"], name=f"fk_{table}_tenant_id_tenant"
        ),
        sa.UniqueConstraint("tenant_id", "id", name=f"uq_{table}_tenant_id_id"),
    ]


def _ts(name: str, nullable: bool = False) -> sa.Column[sa.DateTime]:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=None if nullable else sa.func.now(),
        nullable=nullable,
    )


def _fk(cols: list[str], target: str, name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["tenant_id", *cols], [f"{target}.tenant_id", f"{target}.id"], name=name
    )


def _finish(table: str, privileges: list[str]) -> None:
    enable_tenant_rls(S, table)
    grant_table(S, table, app_role(), privileges)


def upgrade() -> None:
    op.create_table(
        "linear_connect_state",
        *_base("linear_connect_state"),
        sa.Column("state_hash", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        _ts("created_at"),
        _ts("expires_at", nullable=False),
        _ts("used_at", nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["identity.user_account.id"],
            name="fk_linear_connect_state_user_id_user_account",
        ),
        sa.UniqueConstraint(
            "tenant_id", "state_hash", name="uq_linear_connect_state_tenant_id_state_hash"
        ),
        schema=S,
    )
    _finish("linear_connect_state", ["SELECT", "INSERT", "UPDATE"])

    op.create_table(
        "linear_connection",
        *_base("linear_connection"),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("organization_name", sa.Text(), nullable=False),
        sa.Column("url_key", sa.Text(), nullable=True),
        sa.Column("token_ciphertext", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column("connected_by", sa.Uuid(), nullable=False),
        _ts("created_at"),
        _ts("last_synced_at", nullable=True),
        sa.Column("last_sync_status", sa.Text(), server_default="never", nullable=False),
        sa.Column("last_sync_error", sa.Text(), nullable=True),
        _ts("next_reconcile_at", nullable=True),
        sa.ForeignKeyConstraint(
            ["connected_by"],
            ["identity.user_account.id"],
            name="fk_linear_connection_connected_by_user_account",
        ),
        sa.UniqueConstraint(
            "tenant_id", "organization_id", name="uq_linear_connection_tenant_id_organization_id"
        ),
        sa.CheckConstraint(
            "status IN ('active', 'revoked', 'disconnected')",
            name=op.f("ck_linear_connection_status"),
        ),
        sa.CheckConstraint(
            "last_sync_status IN ('never', 'queued', 'ok', 'partial', 'error')",
            name=op.f("ck_linear_connection_last_sync_status"),
        ),
        schema=S,
    )
    _finish("linear_connection", ["SELECT", "INSERT", "UPDATE"])

    op.create_table(
        "linear_team",
        *_base("linear_team"),
        sa.Column("connection_ref", sa.Uuid(), nullable=False),
        sa.Column("linear_id", sa.Text(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=True),
        sa.Column("removed", sa.Boolean(), server_default=sa.false(), nullable=False),
        _fk(["connection_ref"], "integrations.linear_connection", "fk_linear_team_connection"),
        _fk(["team_id"], "directory.team", "fk_linear_team_team"),
        sa.UniqueConstraint("tenant_id", "linear_id", name="uq_linear_team_tenant_id_linear_id"),
        schema=S,
    )
    _finish("linear_team", ["SELECT", "INSERT", "UPDATE"])

    op.create_table(
        "linear_project",
        *_base("linear_project"),
        sa.Column("connection_ref", sa.Uuid(), nullable=False),
        sa.Column("linear_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("lead_linear_id", sa.Text(), nullable=True),
        sa.Column("team_linear_ids", ARRAY(sa.Text()), server_default="{}", nullable=False),
        sa.Column("responsibility_id", sa.Uuid(), nullable=True),
        sa.Column("removed", sa.Boolean(), server_default=sa.false(), nullable=False),
        _ts("updated_at"),
        _fk(["connection_ref"], "integrations.linear_connection", "fk_linear_project_connection"),
        _fk(["responsibility_id"], "catalog.responsibility", "fk_linear_project_responsibility"),
        sa.UniqueConstraint("tenant_id", "linear_id", name="uq_linear_project_tenant_id_linear_id"),
        schema=S,
    )
    _finish("linear_project", ["SELECT", "INSERT", "UPDATE"])

    op.create_table(
        "linear_identity",
        *_base("linear_identity"),
        sa.Column("linear_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("link_status", sa.Text(), server_default="unmatched", nullable=False),
        sa.Column("person_id", sa.Uuid(), nullable=True),
        sa.Column("suggested_person_id", sa.Uuid(), nullable=True),
        sa.Column("match_reason", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        _ts("decided_at", nullable=True),
        _fk(["person_id"], "directory.person", "fk_linear_identity_person"),
        _fk(["suggested_person_id"], "directory.person", "fk_linear_identity_suggested_person"),
        sa.ForeignKeyConstraint(
            ["decided_by"],
            ["identity.user_account.id"],
            name="fk_linear_identity_decided_by_user_account",
        ),
        sa.UniqueConstraint(
            "tenant_id", "linear_id", name="uq_linear_identity_tenant_id_linear_id"
        ),
        sa.CheckConstraint(
            "link_status IN ('unmatched', 'suggested', 'linked', 'dismissed')",
            name=op.f("ck_linear_identity_link_status"),
        ),
        sa.CheckConstraint(
            "(link_status = 'linked') = (person_id IS NOT NULL)",
            name=op.f("ck_linear_identity_linked_person"),
        ),
        schema=S,
    )
    op.create_index(
        "uq_linear_identity_tenant_id_person_id",
        "linear_identity",
        ["tenant_id", "person_id"],
        unique=True,
        schema=S,
        postgresql_where=sa.text("person_id IS NOT NULL"),
    )
    _finish("linear_identity", ["SELECT", "INSERT", "UPDATE"])

    op.create_table(
        "linear_issue",
        *_base("linear_issue"),
        sa.Column("connection_ref", sa.Uuid(), nullable=False),
        sa.Column("linear_id", sa.Text(), nullable=False),
        sa.Column("identifier", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("state_type", sa.Text(), nullable=False),
        sa.Column("state_name", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), server_default="0", nullable=False),
        sa.Column("assignee_linear_id", sa.Text(), nullable=True),
        sa.Column("creator_linear_id", sa.Text(), nullable=True),
        sa.Column("team_linear_id", sa.Text(), nullable=True),
        sa.Column("project_linear_id", sa.Text(), nullable=True),
        sa.Column("parent_identifier", sa.Text(), nullable=True),
        sa.Column("labels", ARRAY(sa.Text()), server_default="{}", nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("li_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("li_updated_at", sa.DateTime(timezone=True), nullable=False),
        _ts("completed_at", nullable=True),
        _ts("canceled_at", nullable=True),
        _fk(["connection_ref"], "integrations.linear_connection", "fk_linear_issue_connection"),
        sa.UniqueConstraint("tenant_id", "linear_id", name="uq_linear_issue_tenant_id_linear_id"),
        sa.CheckConstraint("priority BETWEEN 0 AND 4", name=op.f("ck_linear_issue_priority")),
        schema=S,
    )
    op.create_index(
        "ix_linear_issue_tenant_id_project_linear_id",
        "linear_issue",
        ["tenant_id", "project_linear_id"],
        schema=S,
    )
    _finish("linear_issue", ["SELECT", "INSERT", "UPDATE"])


def downgrade() -> None:
    for table in (
        "linear_issue",
        "linear_identity",
        "linear_project",
        "linear_team",
        "linear_connection",
        "linear_connect_state",
    ):
        op.drop_table(table, schema=S)
