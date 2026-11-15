"""workspace invitations, GitHub integration and ownership suggestions

- identity.invitation: bound to a normalised email; invitees may read their own pending
  invitations through `app.principal_email`, which the server sets only from the
  WorkOS-verified email of the caller.
- directory: optional github_login (person) / github_slug (team) for evidence matching.
- integrations: GitHub connect state (CSRF), installations, repositories and ownership
  suggestions. No GitHub tokens are stored: installation tokens are minted per sync.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from relay.shared.db.migration_ops import app_role, enable_tenant_rls, grant_table

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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


def _user_fk(table: str, column: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["identity.user_account.id"], name=f"fk_{table}_{column}_user_account"
    )


def _tenant_fk(cols: list[str], target: str, name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["tenant_id", *cols], [f"{target}.tenant_id", f"{target}.id"], name=name
    )


def upgrade() -> None:
    role = app_role()

    # ---- invitations
    op.execute(
        """
        CREATE FUNCTION identity.current_principal_email() RETURNS text
        LANGUAGE sql STABLE PARALLEL SAFE
        AS $$ SELECT NULLIF(pg_catalog.current_setting('app.principal_email', true), '') $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION identity.current_principal_email() FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION identity.current_principal_email() TO {role}")
    op.create_table(
        "invitation",
        *_base("invitation"),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("workspace_name", sa.Text(), nullable=False),
        sa.Column("workos_invitation_id", sa.Text()),
        sa.Column("invited_by", sa.Uuid(), nullable=False),
        sa.Column("accepted_by", sa.Uuid()),
        _ts("created_at"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        _ts("decided_at", nullable=True),
        _user_fk("invitation", "invited_by"),
        _user_fk("invitation", "accepted_by"),
        sa.CheckConstraint(
            "email = lower(email) AND email LIKE '%_@_%'", name=op.f("ck_invitation_email")
        ),
        sa.CheckConstraint(
            "role IN ('owner', 'admin', 'member', 'guest', 'auditor')",
            name=op.f("ck_invitation_role"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'revoked')", name=op.f("ck_invitation_status")
        ),
        schema="identity",
    )
    op.create_index(
        "uq_invitation_pending_email",
        "invitation",
        ["tenant_id", "email"],
        unique=True,
        schema="identity",
        postgresql_where=sa.text("status = 'pending'"),
    )
    enable_tenant_rls("identity", "invitation")
    op.execute(
        "CREATE POLICY invitee_read ON identity.invitation FOR SELECT "
        "USING (status = 'pending' AND email = identity.current_principal_email())"
    )
    grant_table("identity", "invitation", role, ["SELECT", "INSERT", "UPDATE"])

    # ---- directory: GitHub handles for evidence matching
    op.add_column("person", sa.Column("github_login", sa.Text()), schema="directory")
    op.add_column("team", sa.Column("github_slug", sa.Text()), schema="directory")
    op.create_index(
        "uq_person_tenant_id_github_login",
        "person",
        ["tenant_id", "github_login"],
        unique=True,
        schema="directory",
        postgresql_where=sa.text("github_login IS NOT NULL"),
    )
    op.create_index(
        "uq_team_tenant_id_github_slug",
        "team",
        ["tenant_id", "github_slug"],
        unique=True,
        schema="directory",
        postgresql_where=sa.text("github_slug IS NOT NULL"),
    )

    # ---- integrations
    op.execute("CREATE SCHEMA integrations")
    op.execute(f"GRANT USAGE ON SCHEMA integrations TO {role}")

    op.create_table(
        "github_connect_state",
        *_base("github_connect_state"),
        sa.Column("state_hash", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        _ts("created_at"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        _ts("used_at", nullable=True),
        _user_fk("github_connect_state", "user_id"),
        sa.UniqueConstraint(
            "tenant_id", "state_hash", name="uq_github_connect_state_tenant_id_state_hash"
        ),
        schema="integrations",
    )

    op.create_table(
        "github_installation",
        *_base("github_installation"),
        sa.Column("installation_id", sa.BigInteger(), nullable=False),
        sa.Column("account_login", sa.Text(), nullable=False),
        sa.Column("account_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column("connected_by", sa.Uuid(), nullable=False),
        _ts("created_at"),
        _ts("last_synced_at", nullable=True),
        sa.Column("last_sync_status", sa.Text(), server_default="never", nullable=False),
        sa.Column("last_sync_error", sa.Text()),
        _user_fk("github_installation", "connected_by"),
        sa.UniqueConstraint(
            "tenant_id", "installation_id", name="uq_github_installation_tenant_id_installation_id"
        ),
        sa.CheckConstraint(
            "status IN ('active', 'revoked', 'disconnected')",
            name=op.f("ck_github_installation_status"),
        ),
        sa.CheckConstraint(
            "last_sync_status IN ('never', 'queued', 'ok', 'partial', 'error')",
            name=op.f("ck_github_installation_last_sync_status"),
        ),
        schema="integrations",
    )

    op.create_table(
        "github_repository",
        *_base("github_repository"),
        sa.Column("installation_ref", sa.Uuid(), nullable=False),
        sa.Column("github_repo_id", sa.BigInteger(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("html_url", sa.Text(), nullable=False),
        sa.Column("default_branch", sa.Text()),
        sa.Column("private", sa.Boolean(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("selected", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("accessible", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("responsibility_id", sa.Uuid()),
        _ts("last_synced_at", nullable=True),
        sa.Column("sync_error", sa.Text()),
        _tenant_fk(
            ["installation_ref"],
            "integrations.github_installation",
            "fk_github_repository_installation",
        ),
        _tenant_fk(
            ["responsibility_id"], "catalog.responsibility", "fk_github_repository_responsibility"
        ),
        sa.UniqueConstraint(
            "tenant_id", "github_repo_id", name="uq_github_repository_tenant_id_github_repo_id"
        ),
        schema="integrations",
    )

    op.create_table(
        "ownership_suggestion",
        *_base("ownership_suggestion"),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("handle", sa.Text(), nullable=False),
        sa.Column("handle_type", sa.Text(), nullable=False),
        sa.Column("proposed_role", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence", JSONB(), nullable=False),
        sa.Column("evidence_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="open", nullable=False),
        sa.Column("decided_by", sa.Uuid()),
        _ts("decided_at", nullable=True),
        sa.Column("assignment_id", sa.Uuid()),
        _ts("created_at"),
        _ts("updated_at"),
        _tenant_fk(
            ["repository_id"],
            "integrations.github_repository",
            "fk_ownership_suggestion_repository",
        ),
        _tenant_fk(
            ["assignment_id"], "catalog.ownership_assignment", "fk_ownership_suggestion_assignment"
        ),
        _user_fk("ownership_suggestion", "decided_by"),
        sa.UniqueConstraint(
            "tenant_id", "repository_id", "handle", name="uq_ownership_suggestion_repository_handle"
        ),
        sa.CheckConstraint(
            "handle_type IN ('user', 'team', 'catalog')",
            name=op.f("ck_ownership_suggestion_handle_type"),
        ),
        sa.CheckConstraint(
            "proposed_role IN ('primary', 'co_owner', 'backup')",
            name=op.f("ck_ownership_suggestion_proposed_role"),
        ),
        sa.CheckConstraint(
            "status IN ('open', 'approved', 'dismissed', 'deferred', 'withdrawn')",
            name=op.f("ck_ownership_suggestion_status"),
        ),
        schema="integrations",
    )

    for table, privileges in (
        ("github_connect_state", ["SELECT", "INSERT", "UPDATE"]),
        ("github_installation", ["SELECT", "INSERT", "UPDATE"]),
        ("github_repository", ["SELECT", "INSERT", "UPDATE"]),
        ("ownership_suggestion", ["SELECT", "INSERT", "UPDATE"]),
    ):
        enable_tenant_rls("integrations", table)
        grant_table("integrations", table, role, privileges)


def downgrade() -> None:
    for table in (
        "ownership_suggestion",
        "github_repository",
        "github_installation",
        "github_connect_state",
    ):
        op.drop_table(table, schema="integrations")
    op.execute("DROP SCHEMA integrations")
    op.drop_index("uq_team_tenant_id_github_slug", table_name="team", schema="directory")
    op.drop_index("uq_person_tenant_id_github_login", table_name="person", schema="directory")
    op.drop_column("team", "github_slug", schema="directory")
    op.drop_column("person", "github_login", schema="directory")
    op.drop_table("invitation", schema="identity")
    op.execute("DROP FUNCTION identity.current_principal_email()")
