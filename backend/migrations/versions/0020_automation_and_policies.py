"""automation center and workspace continuity policies

- governance.workspace_policy: one row per workspace (created on first change; absent =
  defaults). critical_requires_backup and knowledge_review_days drive risks, knowledge
  freshness and insights.
- automation.automation_rule: one per template per workspace; enabled, action (notify or
  create a follow-up), optional assignee, schedule state.
- automation.automation_run: execution history (trigger, status, counts, error).
- automation.automation_action: idempotency ledger; unique per (rule, dedupe key), so a
  retried or repeated run never notifies or creates a follow-up twice.
- automation.follow_up: lightweight tasks created by automations (shown in My Work).
- notifications.notification: may now point at a responsibility instead of a case
  (kind 'automation'); case_id becomes nullable (expand only).

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from relay.shared.db.migration_ops import app_role, enable_tenant_rls, grant_table

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

A = "automation"
OLD_KINDS = (
    "task_assigned",
    "task_due_soon",
    "task_overdue",
    "approval_requested",
    "mentioned",
    "case_update",
)
TEMPLATES = (
    "critical_without_backup",
    "no_primary_owner",
    "stale_knowledge",
    "archived_owner",
    "coverage_ending",
    "case_overdue",
    "task_overdue",
    "risk_acceptance_expiring",
)


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


def _user(table: str, column: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["identity.user_account.id"], name=f"fk_{table}_{column}_user_account"
    )


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    role = app_role()
    for schema in ("governance", A):
        op.execute(f"CREATE SCHEMA {schema}")
        op.execute(f"GRANT USAGE ON SCHEMA {schema} TO {role}")

    op.create_table(
        "workspace_policy",
        *_base("workspace_policy"),
        sa.Column(
            "critical_requires_backup", sa.Boolean(), server_default=sa.true(), nullable=False
        ),
        sa.Column("knowledge_review_days", sa.Integer(), server_default="90", nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        _ts("updated_at"),
        _user("workspace_policy", "updated_by"),
        sa.UniqueConstraint("tenant_id", name="uq_workspace_policy_tenant_id"),
        sa.CheckConstraint(
            "knowledge_review_days BETWEEN 7 AND 730",
            name=op.f("ck_workspace_policy_knowledge_review_days"),
        ),
        schema="governance",
    )
    enable_tenant_rls("governance", "workspace_policy")
    grant_table("governance", "workspace_policy", role, ["SELECT", "INSERT", "UPDATE"])

    op.create_table(
        "automation_rule",
        *_base("automation_rule"),
        sa.Column("template", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("action", sa.Text(), server_default="notify", nullable=False),
        sa.Column("assignee_user_id", sa.Uuid(), nullable=True),
        _ts("last_run_at", nullable=True),
        sa.Column("last_status", sa.Text(), server_default="never", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        _ts("next_run_at", nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        _ts("updated_at"),
        _user("automation_rule", "assignee_user_id"),
        _user("automation_rule", "updated_by"),
        sa.UniqueConstraint("tenant_id", "template", name="uq_automation_rule_tenant_id_template"),
        sa.CheckConstraint(_in("template", TEMPLATES), name=op.f("ck_automation_rule_template")),
        sa.CheckConstraint(
            "action IN ('notify', 'create_follow_up')", name=op.f("ck_automation_rule_action")
        ),
        sa.CheckConstraint(
            "last_status IN ('never', 'ok', 'failed')", name=op.f("ck_automation_rule_last_status")
        ),
        schema=A,
    )
    enable_tenant_rls(A, "automation_rule")
    grant_table(A, "automation_rule", role, ["SELECT", "INSERT", "UPDATE"])

    op.create_table(
        "automation_run",
        *_base("automation_run"),
        sa.Column("rule_id", sa.Uuid(), nullable=False),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("matched", sa.Integer(), server_default="0", nullable=False),
        sa.Column("actions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        _ts("started_at"),
        _ts("finished_at", nullable=True),
        _fk(["rule_id"], "automation.automation_rule", "fk_automation_run_rule"),
        sa.CheckConstraint(
            "trigger IN ('schedule', 'manual', 'retry')", name=op.f("ck_automation_run_trigger")
        ),
        sa.CheckConstraint("status IN ('ok', 'failed')", name=op.f("ck_automation_run_status")),
        schema=A,
    )
    op.create_index(
        "ix_automation_run_tenant_id_rule_id", "automation_run", ["tenant_id", "rule_id"], schema=A
    )
    enable_tenant_rls(A, "automation_run")
    grant_table(A, "automation_run", role, ["SELECT", "INSERT", "UPDATE"])

    op.create_table(
        "follow_up",
        *_base("follow_up"),
        sa.Column("rule_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("responsibility_id", sa.Uuid(), nullable=True),
        sa.Column("case_id", sa.Uuid(), nullable=True),
        sa.Column("assignee_user_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.Text(), server_default="open", nullable=False),
        _ts("created_at"),
        sa.Column("completed_by", sa.Uuid(), nullable=True),
        _ts("completed_at", nullable=True),
        _fk(["rule_id"], "automation.automation_rule", "fk_follow_up_rule"),
        _fk(["responsibility_id"], "catalog.responsibility", "fk_follow_up_responsibility"),
        _fk(["case_id"], "continuity.continuity_case", "fk_follow_up_case"),
        _user("follow_up", "assignee_user_id"),
        _user("follow_up", "completed_by"),
        sa.CheckConstraint("status IN ('open', 'done')", name=op.f("ck_follow_up_status")),
        sa.CheckConstraint(
            "num_nonnulls(responsibility_id, case_id) = 1", name=op.f("ck_follow_up_subject")
        ),
        schema=A,
    )
    enable_tenant_rls(A, "follow_up")
    grant_table(A, "follow_up", role, ["SELECT", "INSERT", "UPDATE"])

    op.create_table(
        "automation_action",
        *_base("automation_action"),
        sa.Column("rule_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("dedupe_key", sa.Text(), nullable=False),
        sa.Column("follow_up_id", sa.Uuid(), nullable=True),
        _ts("created_at"),
        _fk(["rule_id"], "automation.automation_rule", "fk_automation_action_rule"),
        _fk(["run_id"], "automation.automation_run", "fk_automation_action_run"),
        _fk(["follow_up_id"], "automation.follow_up", "fk_automation_action_follow_up"),
        sa.UniqueConstraint(
            "tenant_id",
            "rule_id",
            "dedupe_key",
            name="uq_automation_action_tenant_id_rule_id_dedupe_key",
        ),
        schema=A,
    )
    enable_tenant_rls(A, "automation_action")
    grant_table(A, "automation_action", role, ["SELECT", "INSERT", "UPDATE"])

    # Notifications about a responsibility (automation alerts) rather than a case.
    n = "notifications"
    op.alter_column("notification", "case_id", nullable=True, schema=n)
    op.add_column(
        "notification", sa.Column("responsibility_id", sa.Uuid(), nullable=True), schema=n
    )
    op.create_foreign_key(
        "fk_notification_responsibility",
        "notification",
        "responsibility",
        ["tenant_id", "responsibility_id"],
        ["tenant_id", "id"],
        source_schema=n,
        referent_schema="catalog",
    )
    op.drop_constraint("ck_notification_kind", "notification", schema=n)
    op.create_check_constraint(
        op.f("ck_notification_kind"),
        "notification",
        _in("kind", (*OLD_KINDS, "automation")),
        schema=n,
    )
    op.create_check_constraint(
        op.f("ck_notification_subject"),
        "notification",
        "num_nonnulls(case_id, responsibility_id) >= 1",
        schema=n,
    )


def downgrade() -> None:
    n = "notifications"
    op.execute("DELETE FROM notifications.notification WHERE case_id IS NULL")
    op.drop_constraint("ck_notification_subject", "notification", schema=n)
    op.drop_constraint("ck_notification_kind", "notification", schema=n)
    op.create_check_constraint(
        op.f("ck_notification_kind"), "notification", _in("kind", OLD_KINDS), schema=n
    )
    op.drop_constraint("fk_notification_responsibility", "notification", schema=n)
    op.drop_column("notification", "responsibility_id", schema=n)
    op.alter_column("notification", "case_id", nullable=False, schema=n)
    for table in ("automation_action", "follow_up", "automation_run", "automation_rule"):
        op.drop_table(table, schema=A)
    op.drop_table("workspace_policy", schema="governance")
    op.execute(f"DROP SCHEMA {A}")
    op.execute("DROP SCHEMA governance")
