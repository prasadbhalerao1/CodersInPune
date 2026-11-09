"""task coordination and readiness states

- case_task: priority, team assignee, open clarification (who must answer), completion
  evidence (note and link), and fields for mirroring to an external tracker (provider,
  external id/url, sync status). Mirroring itself is approved and run in M10.
- case_task_dependency: a task waits for another task in the same case.
- case_task_event: append-only task activity: comments, clarification requests and
  answers, reassignments (with reason), due-date changes, completion and reopening.
- case_readiness_criterion: statuses needs_review and unable_to_assess (both need a note,
  like blocked); type rehearsal with a supervised checklist.

Revision ID: 0024
Revises: 0023
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from relay.shared.db.migration_ops import app_role, enable_tenant_rls, grant_table

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

C = "continuity"
TASK = "case_task"
CRIT = "case_readiness_criterion"
OLD_CRIT_TYPES = (
    "attestation",
    "task_completed",
    "artefact_linked",
    "supervised_demo",
    "access_confirmed",
    "qa_reviewed",
)
CRIT_TYPES = (*OLD_CRIT_TYPES, "rehearsal")
OLD_CRIT_STATUSES = ("pending", "met", "blocked", "waived")
CRIT_STATUSES = (*OLD_CRIT_STATUSES, "needs_review", "unable_to_assess")
EVENT_KINDS = (
    "comment",
    "clarification_requested",
    "clarification_answered",
    "reassigned",
    "due_changed",
    "completed",
    "reopened",
    "cancelled",
)


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _replace_check(table: str, name: str, condition: str) -> None:
    op.drop_constraint(f"ck_{table}_{name}", table, schema=C)
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, condition, schema=C)


def _user_fk(table: str, column: str) -> None:
    op.create_foreign_key(
        f"fk_{table}_{column}_user_account",
        table,
        "user_account",
        [column],
        ["id"],
        source_schema=C,
        referent_schema="identity",
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


def _task_fk(table: str, column: str, name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["tenant_id", column],
        ["continuity.case_task.tenant_id", "continuity.case_task.id"],
        name=name,
    )


def upgrade() -> None:
    role = app_role()
    text = sa.Text()
    add = op.add_column
    add(TASK, sa.Column("priority", text, server_default="normal", nullable=False), schema=C)
    add(TASK, sa.Column("assignee_team_id", sa.Uuid(), nullable=True), schema=C)
    add(TASK, sa.Column("needs_input_from_user_id", sa.Uuid(), nullable=True), schema=C)
    add(TASK, sa.Column("completion_note", text, nullable=True), schema=C)
    add(TASK, sa.Column("completion_url", text, nullable=True), schema=C)
    add(TASK, sa.Column("external_provider", text, nullable=True), schema=C)
    add(TASK, sa.Column("external_id", text, nullable=True), schema=C)
    add(TASK, sa.Column("external_url", text, nullable=True), schema=C)
    add(
        TASK,
        sa.Column("sync_status", text, server_default="not_mirrored", nullable=False),
        schema=C,
    )
    op.create_foreign_key(
        "fk_case_task_assignee_team",
        TASK,
        "team",
        ["tenant_id", "assignee_team_id"],
        ["tenant_id", "id"],
        source_schema=C,
        referent_schema="directory",
    )
    _user_fk(TASK, "needs_input_from_user_id")
    for name, condition in (
        ("priority", _in("priority", ("low", "normal", "high", "urgent"))),
        (
            "sync_status",
            _in("sync_status", ("not_mirrored", "pending", "synced", "error", "unlinked")),
        ),
        (
            "external_provider",
            "external_provider IS NULL OR external_provider IN ('github', 'linear')",
        ),
        ("completion_url_scheme", "completion_url IS NULL OR completion_url ~ '^https?://'"),
        ("external_url_scheme", "external_url IS NULL OR external_url ~ '^https?://'"),
        ("one_assignee", "num_nonnulls(assignee_user_id, assignee_team_id) <= 1"),
    ):
        op.create_check_constraint(op.f(f"ck_{TASK}_{name}"), TASK, condition, schema=C)

    t = "case_task_dependency"
    op.create_table(
        t,
        *_base(t),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("depends_on_task_id", sa.Uuid(), nullable=False),
        _task_fk(t, "task_id", "fk_case_task_dependency_task"),
        _task_fk(t, "depends_on_task_id", "fk_case_task_dependency_depends_on"),
        sa.CheckConstraint("task_id <> depends_on_task_id", name=op.f(f"ck_{t}_not_self")),
        sa.UniqueConstraint(
            "tenant_id",
            "task_id",
            "depends_on_task_id",
            name="uq_case_task_dependency_tenant_id_task_id_depends_on_task_id",
        ),
        schema=C,
    )

    t = "case_task_event"
    op.create_table(
        t,
        *_base(t),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("kind", text, nullable=False),
        sa.Column("body", text, nullable=True),
        sa.Column("detail", JSONB(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        _task_fk(t, "task_id", "fk_case_task_event_task"),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["identity.user_account.id"],
            name=f"fk_{t}_actor_user_id_user_account",
        ),
        sa.CheckConstraint(_in("kind", EVENT_KINDS), name=op.f(f"ck_{t}_kind")),
        sa.CheckConstraint(
            "body IS NULL OR char_length(body) BETWEEN 1 AND 5000", name=op.f(f"ck_{t}_body_length")
        ),
        schema=C,
    )
    op.create_index(f"ix_{t}_tenant_id_task_id", t, ["tenant_id", "task_id"], schema=C)

    add(
        CRIT,
        sa.Column("checklist", JSONB(), server_default=sa.text("'[]'"), nullable=False),
        schema=C,
    )
    _replace_check(CRIT, "type", _in("criterion_type", CRIT_TYPES))
    _replace_check(CRIT, "status", _in("status", CRIT_STATUSES))
    op.create_check_constraint(
        op.f(f"ck_{CRIT}_explained"),
        CRIT,
        "status NOT IN ('blocked', 'needs_review', 'unable_to_assess') OR note IS NOT NULL",
        schema=C,
    )

    enable_tenant_rls(C, "case_task_dependency")
    grant_table(C, "case_task_dependency", role, ["SELECT", "INSERT", "DELETE"])
    enable_tenant_rls(C, "case_task_event")
    grant_table(C, "case_task_event", role, ["SELECT", "INSERT"])  # append-only


def downgrade() -> None:
    op.drop_constraint(f"ck_{CRIT}_explained", CRIT, schema=C)
    _replace_check(CRIT, "status", _in("status", OLD_CRIT_STATUSES))
    _replace_check(CRIT, "type", _in("criterion_type", OLD_CRIT_TYPES))
    op.drop_column(CRIT, "checklist", schema=C)
    op.drop_table("case_task_event", schema=C)
    op.drop_table("case_task_dependency", schema=C)
    for name in (
        "priority",
        "sync_status",
        "external_provider",
        "completion_url_scheme",
        "external_url_scheme",
        "one_assignee",
    ):
        op.drop_constraint(f"ck_{TASK}_{name}", TASK, schema=C)
    op.drop_constraint(f"fk_{TASK}_needs_input_from_user_id_user_account", TASK, schema=C)
    op.drop_constraint("fk_case_task_assignee_team", TASK, schema=C)
    for column in (
        "sync_status",
        "external_url",
        "external_id",
        "external_provider",
        "completion_url",
        "completion_note",
        "needs_input_from_user_id",
        "assignee_team_id",
        "priority",
    ):
        op.drop_column(TASK, column, schema=C)
