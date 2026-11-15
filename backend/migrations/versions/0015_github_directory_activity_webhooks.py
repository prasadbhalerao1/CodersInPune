"""GitHub: identities, teams, PR/issue metadata, webhook deliveries and routing

- github_identity: GitHub users seen in evidence; linked to a Relay person only by an
  explicit decision (one identity per person, enforced). Suggestions never merge people.
- github_team / github_team_member: organisation teams and their members.
- github_work_item: pull request and issue *metadata* (no bodies, no code).
- webhook_delivery: received deliveries, unique per X-GitHub-Delivery (dedupe).
- github_installation_route: installation id -> workspace, so an unauthenticated webhook
  (verified by HMAC) can be routed. Readable only outside a tenant context (the router);
  inside a tenant session it behaves like any other tenant table.
- github_repository.pushed_at / last_activity_at for staleness signals.

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

from relay.shared.db.migration_ops import app_role, enable_tenant_rls, grant_table

revision: str = "0015"
down_revision: str | None = "0014"
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
        "github_identity",
        *_base("github_identity"),
        sa.Column("github_user_id", sa.BigInteger(), nullable=False),
        sa.Column("login", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("public_email", sa.Text(), nullable=True),
        sa.Column("link_status", sa.Text(), server_default="unmatched", nullable=False),
        sa.Column("person_id", sa.Uuid(), nullable=True),
        sa.Column("suggested_person_id", sa.Uuid(), nullable=True),
        sa.Column("match_reason", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        _ts("decided_at", nullable=True),
        _ts("first_seen_at"),
        _ts("updated_at"),
        _fk(["person_id"], "directory.person", "fk_github_identity_person"),
        _fk(["suggested_person_id"], "directory.person", "fk_github_identity_suggested_person"),
        sa.ForeignKeyConstraint(
            ["decided_by"],
            ["identity.user_account.id"],
            name="fk_github_identity_decided_by_user_account",
        ),
        sa.UniqueConstraint(
            "tenant_id", "github_user_id", name="uq_github_identity_tenant_id_github_user_id"
        ),
        sa.CheckConstraint(
            "link_status IN ('unmatched', 'suggested', 'linked', 'dismissed')",
            name=op.f("ck_github_identity_link_status"),
        ),
        sa.CheckConstraint(
            "(link_status = 'linked') = (person_id IS NOT NULL)",
            name=op.f("ck_github_identity_linked_person"),
        ),
        schema=S,
    )
    # One GitHub identity per Relay person: linking can never merge two people.
    op.create_index(
        "uq_github_identity_tenant_id_person_id",
        "github_identity",
        ["tenant_id", "person_id"],
        unique=True,
        schema=S,
        postgresql_where=sa.text("person_id IS NOT NULL"),
    )
    _finish("github_identity", ["SELECT", "INSERT", "UPDATE"])

    op.create_table(
        "github_team",
        *_base("github_team"),
        sa.Column("installation_ref", sa.Uuid(), nullable=False),
        sa.Column("github_team_id", sa.BigInteger(), nullable=False),
        sa.Column("org_login", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=True),
        sa.Column("removed", sa.Boolean(), server_default=sa.false(), nullable=False),
        _ts("updated_at"),
        _fk(
            ["installation_ref"], "integrations.github_installation", "fk_github_team_installation"
        ),
        _fk(["team_id"], "directory.team", "fk_github_team_team"),
        sa.UniqueConstraint(
            "tenant_id", "github_team_id", name="uq_github_team_tenant_id_github_team_id"
        ),
        schema=S,
    )
    _finish("github_team", ["SELECT", "INSERT", "UPDATE"])

    op.create_table(
        "github_team_member",
        *_base("github_team_member"),
        sa.Column("github_team_ref", sa.Uuid(), nullable=False),
        sa.Column("identity_ref", sa.Uuid(), nullable=False),
        _fk(["github_team_ref"], "integrations.github_team", "fk_github_team_member_team"),
        _fk(["identity_ref"], "integrations.github_identity", "fk_github_team_member_identity"),
        sa.UniqueConstraint(
            "tenant_id",
            "github_team_ref",
            "identity_ref",
            name="uq_github_team_member_tenant_id_github_team_ref_identity_ref",
        ),
        schema=S,
    )
    _finish("github_team_member", ["SELECT", "INSERT", "DELETE"])

    op.create_table(
        "github_work_item",
        *_base("github_work_item"),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("github_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("author_login", sa.Text(), nullable=True),
        sa.Column("assignee_logins", ARRAY(sa.Text()), server_default="{}", nullable=False),
        sa.Column("reviewer_logins", ARRAY(sa.Text()), server_default="{}", nullable=False),
        sa.Column("labels", ARRAY(sa.Text()), server_default="{}", nullable=False),
        sa.Column("html_url", sa.Text(), nullable=False),
        sa.Column("gh_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("gh_updated_at", sa.DateTime(timezone=True), nullable=False),
        _ts("closed_at", nullable=True),
        _ts("merged_at", nullable=True),
        _fk(["repository_id"], "integrations.github_repository", "fk_github_work_item_repository"),
        sa.UniqueConstraint(
            "tenant_id",
            "repository_id",
            "kind",
            "number",
            name="uq_github_work_item_tenant_id_repository_id_kind_number",
        ),
        sa.CheckConstraint(
            "kind IN ('pull_request', 'issue')", name=op.f("ck_github_work_item_kind")
        ),
        sa.CheckConstraint(
            "state IN ('open', 'closed', 'merged')", name=op.f("ck_github_work_item_state")
        ),
        schema=S,
    )
    op.create_index(
        "ix_github_work_item_tenant_id_repository_id_gh_updated_at",
        "github_work_item",
        ["tenant_id", "repository_id", "gh_updated_at"],
        schema=S,
    )
    _finish("github_work_item", ["SELECT", "INSERT", "UPDATE"])

    op.create_table(
        "webhook_delivery",
        *_base("webhook_delivery"),
        sa.Column("delivery_id", sa.Text(), nullable=False),
        sa.Column("event", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=True),
        _ts("received_at"),
        sa.UniqueConstraint(
            "tenant_id", "delivery_id", name="uq_webhook_delivery_tenant_id_delivery_id"
        ),
        schema=S,
    )
    _finish("webhook_delivery", ["SELECT", "INSERT"])

    op.create_table(
        "github_installation_route",
        *_base("github_installation_route"),
        sa.Column("installation_id", sa.BigInteger(), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "installation_id",
            name="uq_github_installation_route_tenant_id_installation_id",
        ),
        schema=S,
    )
    _finish("github_installation_route", ["SELECT", "INSERT", "DELETE"])
    op.execute(
        f"CREATE POLICY route_lookup ON {S}.github_installation_route FOR SELECT "
        "USING (platform.current_tenant_id() IS NULL)"
    )
    # No backfill here: forced RLS hides tenant rows from the migration role. Routes are
    # (re)written by the app inside each tenant's context on connect and on every sync.

    op.add_column("github_repository", _ts("pushed_at", nullable=True), schema=S)
    op.add_column("github_repository", _ts("last_activity_at", nullable=True), schema=S)


def downgrade() -> None:
    op.drop_column("github_repository", "last_activity_at", schema=S)
    op.drop_column("github_repository", "pushed_at", schema=S)
    for table in (
        "github_installation_route",
        "webhook_delivery",
        "github_work_item",
        "github_team_member",
        "github_team",
        "github_identity",
    ):
        op.drop_table(table, schema=S)
