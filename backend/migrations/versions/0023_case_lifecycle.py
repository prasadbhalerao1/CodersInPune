"""full case lifecycle: onboarding and project handover, status model, blockers, participants

- continuity_case: case types onboarding/project_handover; the SRS statuses (investigating,
  awaiting_input, awaiting_review, ready_for_transfer, verification, blocked, reopened);
  priority, due date (separate from the effective date), time zone, accountable manager,
  delegated approver and approval deadline, parent case (departure split), project asset
  (project handover), duplicate-override reason, reopen count and `blocked_from`.
- case_status_change: append-only status history (actor, time, reason, closure snapshot).
- case_participant: explicit participants and why each is involved.
- case_blocker: blockers with an escalation time; resolving the last one unblocks the case.
- case_scope_item: the incoming owner may decline (reason kept; the recipient is cleared).
- governance.saved_view: per-user saved filters for list pages.

Revision ID: 0023
Revises: 0022
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from relay.shared.db.migration_ops import app_role, enable_tenant_rls, grant_table

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

C = "continuity"
CASE = "continuity_case"
OLD_TYPES = ("transfer", "coverage", "departure")
TYPES = (*OLD_TYPES, "onboarding", "project_handover")
OLD_STATUSES = ("draft", "planning", "executing", "completed", "cancelled")
STATUSES = (
    "draft",
    "investigating",
    "awaiting_input",
    "planning",
    "awaiting_review",
    "ready_for_transfer",
    "executing",
    "verification",
    "blocked",
    "reopened",
    "completed",
    "cancelled",
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


def _text(name: str, nullable: bool = False, default: str | None = None) -> sa.Column[sa.Text]:
    return sa.Column(name, sa.Text(), server_default=default, nullable=nullable)


def _uuid(name: str, nullable: bool = False) -> sa.Column[sa.Uuid]:
    return sa.Column(name, sa.Uuid(), nullable=nullable)


def _fk(table: str, cols: list[str], target: str, name: str) -> None:
    op.create_foreign_key(
        name,
        table,
        target.split(".")[1],
        ["tenant_id", *cols],
        ["tenant_id", "id"],
        source_schema=C,
        referent_schema=target.split(".")[0],
    )


def _fk_def(cols: list[str], target: str, name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["tenant_id", *cols], [f"{target}.tenant_id", f"{target}.id"], name=name
    )


def _user(table: str, column: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["identity.user_account.id"], name=f"fk_{table}_{column}_user_account"
    )


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _replace_check(table: str, name: str, condition: str, schema: str = C) -> None:
    op.drop_constraint(f"ck_{table}_{name}", table, schema=schema)
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, condition, schema=schema)


def upgrade() -> None:
    role = app_role()
    add = op.add_column
    add(CASE, _text("priority", default="normal"), schema=C)
    add(CASE, _ts("due_at", nullable=True), schema=C)
    add(CASE, _text("time_zone", default="UTC"), schema=C)
    add(CASE, _uuid("accountable_manager_user_id", nullable=True), schema=C)
    add(CASE, _uuid("delegate_approver_user_id", nullable=True), schema=C)
    add(CASE, _ts("approval_due_at", nullable=True), schema=C)
    add(CASE, _uuid("parent_case_id", nullable=True), schema=C)
    add(CASE, _uuid("project_asset_id", nullable=True), schema=C)
    add(CASE, _text("duplicate_override_reason", nullable=True), schema=C)
    add(CASE, sa.Column("reopen_count", sa.Integer(), server_default="0", nullable=False), schema=C)
    add(CASE, _text("blocked_from", nullable=True), schema=C)
    for column in ("accountable_manager_user_id", "delegate_approver_user_id"):
        op.create_foreign_key(
            f"fk_{CASE}_{column}_user_account",
            CASE,
            "user_account",
            [column],
            ["id"],
            source_schema=C,
            referent_schema="identity",
        )
    _fk(CASE, ["parent_case_id"], "continuity.continuity_case", "fk_case_parent_case")
    _fk(CASE, ["project_asset_id"], "catalog.asset", "fk_case_project_asset")
    _replace_check(CASE, "case_type", _in("case_type", TYPES))
    _replace_check(CASE, "status", _in("status", STATUSES))
    _replace_check(
        CASE,
        "affected_person",
        "case_type IN ('transfer', 'project_handover') OR affected_person_id IS NOT NULL",
    )
    for name, condition in (
        ("priority", _in("priority", ("low", "normal", "high", "urgent"))),
        ("blocked_from", "(status = 'blocked') = (blocked_from IS NOT NULL)"),
        ("project_asset", "case_type = 'project_handover' OR project_asset_id IS NULL"),
        ("time_zone_length", "char_length(time_zone) BETWEEN 1 AND 64"),
    ):
        op.create_check_constraint(op.f(f"ck_{CASE}_{name}"), CASE, condition, schema=C)
    op.create_index(
        f"ix_{CASE}_tenant_id_affected_person_id",
        CASE,
        ["tenant_id", "affected_person_id"],
        schema=C,
    )

    item = "case_scope_item"
    add(item, _ts("declined_at", nullable=True), schema=C)
    add(item, _uuid("declined_by", nullable=True), schema=C)
    add(item, _text("decline_reason", nullable=True), schema=C)
    op.create_foreign_key(
        f"fk_{item}_declined_by_user_account",
        item,
        "user_account",
        ["declined_by"],
        ["id"],
        source_schema=C,
        referent_schema="identity",
    )

    t = "case_status_change"
    op.create_table(
        t,
        *_base(t),
        _uuid("case_id"),
        _text("from_status", nullable=True),
        _text("to_status"),
        _text("reason", nullable=True),
        _text("outcome", nullable=True),
        _ts("closed_at", nullable=True),
        _uuid("actor_user_id"),
        _ts("changed_at"),
        _fk_def(["case_id"], "continuity.continuity_case", "fk_case_status_change_case"),
        _user(t, "actor_user_id"),
        sa.CheckConstraint(_in("to_status", STATUSES), name=op.f(f"ck_{t}_to_status")),
        schema=C,
    )
    op.create_index(f"ix_{t}_tenant_id_case_id", t, ["tenant_id", "case_id"], schema=C)

    t = "case_participant"
    op.create_table(
        t,
        *_base(t),
        _uuid("case_id"),
        _uuid("user_id", nullable=True),
        _uuid("person_id", nullable=True),
        _text("role"),
        _text("why"),
        _uuid("added_by"),
        _ts("added_at"),
        _fk_def(["case_id"], "continuity.continuity_case", "fk_case_participant_case"),
        _fk_def(["person_id"], "directory.person", "fk_case_participant_person"),
        _user(t, "user_id"),
        _user(t, "added_by"),
        sa.CheckConstraint(
            _in("role", ("approver", "verifier", "reviewer", "contributor", "observer")),
            name=op.f(f"ck_{t}_role"),
        ),
        sa.CheckConstraint(
            "num_nonnulls(user_id, person_id) = 1", name=op.f(f"ck_{t}_one_subject")
        ),
        sa.CheckConstraint("char_length(why) BETWEEN 1 AND 500", name=op.f(f"ck_{t}_why_length")),
        schema=C,
    )

    t = "case_blocker"
    op.create_table(
        t,
        *_base(t),
        _uuid("case_id"),
        _text("description"),
        _uuid("owner_user_id", nullable=True),
        _ts("escalate_at"),
        _ts("escalated_at", nullable=True),
        _text("resolution", nullable=True),
        _uuid("resolved_by", nullable=True),
        _ts("resolved_at", nullable=True),
        _uuid("created_by"),
        _ts("created_at"),
        _fk_def(["case_id"], "continuity.continuity_case", "fk_case_blocker_case"),
        _user(t, "owner_user_id"),
        _user(t, "resolved_by"),
        _user(t, "created_by"),
        sa.CheckConstraint(
            "char_length(description) BETWEEN 1 AND 1000", name=op.f(f"ck_{t}_description_length")
        ),
        sa.CheckConstraint(
            "(resolved_at IS NULL) = (resolution IS NULL)", name=op.f(f"ck_{t}_resolution")
        ),
        schema=C,
    )

    t = "saved_view"
    op.create_table(
        t,
        *_base(t),
        _uuid("user_id"),
        _text("page"),
        _text("name"),
        _text("query"),
        _ts("created_at"),
        _user(t, "user_id"),
        sa.CheckConstraint(
            _in("page", ("cases", "responsibilities", "assets", "knowledge")),
            name=op.f(f"ck_{t}_page"),
        ),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 80", name=op.f(f"ck_{t}_name_length")),
        sa.CheckConstraint("char_length(query) <= 1000", name=op.f(f"ck_{t}_query_length")),
        sa.UniqueConstraint(
            "tenant_id", "user_id", "page", "name", name="uq_saved_view_tenant_id_user_id_page_name"
        ),
        schema="governance",
    )

    enable_tenant_rls(C, "case_status_change")
    grant_table(C, "case_status_change", role, ["SELECT", "INSERT"])  # append-only
    enable_tenant_rls(C, "case_participant")
    grant_table(C, "case_participant", role, ["SELECT", "INSERT", "DELETE"])
    enable_tenant_rls(C, "case_blocker")
    grant_table(C, "case_blocker", role, ["SELECT", "INSERT", "UPDATE"])
    enable_tenant_rls("governance", "saved_view")
    grant_table("governance", "saved_view", role, ["SELECT", "INSERT", "DELETE"])


def downgrade() -> None:
    op.drop_table("saved_view", schema="governance")
    for table in ("case_blocker", "case_participant", "case_status_change"):
        op.drop_table(table, schema=C)
    item = "case_scope_item"
    op.drop_constraint(f"fk_{item}_declined_by_user_account", item, schema=C)
    for column in ("decline_reason", "declined_by", "declined_at"):
        op.drop_column(item, column, schema=C)
    op.drop_index(f"ix_{CASE}_tenant_id_affected_person_id", CASE, schema=C)
    for name in ("priority", "blocked_from", "project_asset", "time_zone_length"):
        op.drop_constraint(f"ck_{CASE}_{name}", CASE, schema=C)
    # Map the new vocabulary back onto the old one before narrowing the checks.
    op.execute(
        f"UPDATE {C}.{CASE} SET status = CASE "
        "WHEN status IN ('investigating', 'awaiting_input', 'reopened') THEN 'draft' "
        "WHEN status IN ('awaiting_review', 'ready_for_transfer') THEN 'planning' "
        "WHEN status = 'verification' THEN 'executing' "
        "WHEN status = 'blocked' THEN blocked_from ELSE status END"
    )
    op.execute(
        f"UPDATE {C}.{CASE} SET case_type = 'transfer' "
        "WHERE case_type IN ('onboarding', 'project_handover')"
    )
    _replace_check(CASE, "status", _in("status", OLD_STATUSES))
    _replace_check(CASE, "case_type", _in("case_type", OLD_TYPES))
    _replace_check(
        CASE, "affected_person", "case_type = 'transfer' OR affected_person_id IS NOT NULL"
    )
    op.drop_constraint("fk_case_project_asset", CASE, schema=C)
    op.drop_constraint("fk_case_parent_case", CASE, schema=C)
    for column in ("accountable_manager_user_id", "delegate_approver_user_id"):
        op.drop_constraint(f"fk_{CASE}_{column}_user_account", CASE, schema=C)
    for column in (
        "blocked_from",
        "reopen_count",
        "duplicate_override_reason",
        "project_asset_id",
        "parent_case_id",
        "approval_due_at",
        "delegate_approver_user_id",
        "accountable_manager_user_id",
        "time_zone",
        "due_at",
        "priority",
    ):
        op.drop_column(CASE, column, schema=C)
