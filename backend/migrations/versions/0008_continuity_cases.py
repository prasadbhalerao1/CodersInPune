"""continuity cases, temporary coverage role, member display profiles

- catalog: `temporary` role (always bounded; at most one at a time; may overlap the same
  assignee's normal role) and an `extended` change type for coverage extensions.
- identity.membership: self-reported display_name/email for showing members in the UI.
- continuity schema: case, scope item, task, readiness criterion, approval.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from relay.shared.db.migration_ops import app_role, enable_tenant_rls, grant_table

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERIOD = "tstzrange(valid_from, valid_to, '[)')"
OA = "catalog.ownership_assignment"


def _ts(name: str, nullable: bool = False) -> sa.Column[sa.DateTime]:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=None if nullable else sa.func.now(),
        nullable=nullable,
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


def _fk(cols: list[str], target: str, name: str) -> sa.ForeignKeyConstraint:
    """Composite (tenant_id, col) foreign key to a tenant-scoped table's (tenant_id, id)."""
    schema_table = target.rsplit(".", 1)[0]
    return sa.ForeignKeyConstraint(
        ["tenant_id", *cols],
        [f"{schema_table}.tenant_id", f"{schema_table}.id"],
        name=name,
    )


def _user_fk(table: str, column: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["identity.user_account.id"], name=f"fk_{table}_{column}_user_account"
    )


def upgrade() -> None:
    role = app_role()

    # ---- fix earlier CHECK names: Alembic applied the ck naming convention on top of the
    # explicit names in 0003-0007 (ck_<t>_ck_<t>_x). Rename them to ck_<t>_x. New migrations
    # pass op.f("ck_...") to mark names as final.
    op.execute(
        r"""
        DO $$ DECLARE r record; BEGIN
            FOR r IN
                SELECT n.nspname AS s, c.relname AS t, k.conname AS old,
                       substring(k.conname FROM char_length('ck_' || c.relname || '_') + 1) AS new
                FROM pg_constraint k
                JOIN pg_class c ON c.oid = k.conrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE k.contype = 'c' AND k.conname LIKE 'ck\_' || c.relname || '\_ck\_%'
                  AND char_length(k.conname) < 63
            LOOP
                EXECUTE format(
                    'ALTER TABLE %I.%I RENAME CONSTRAINT %I TO %I', r.s, r.t, r.old, r.new
                );
            END LOOP;
        END $$
        """
    )
    # The one truncated name (change_type on the change table) is replaced below.
    op.execute(
        """
        DO $$ DECLARE r record; BEGIN
            FOR r IN SELECT conname FROM pg_constraint
                     WHERE conrelid = 'catalog.ownership_assignment_change'::regclass
                       AND contype = 'c' AND pg_get_constraintdef(oid) LIKE '%change_type%'
            LOOP
                EXECUTE format(
                    'ALTER TABLE catalog.ownership_assignment_change DROP CONSTRAINT %I', r.conname
                );
            END LOOP;
        END $$
        """
    )

    # ---- catalog: temporary coverage
    op.execute(f"ALTER TABLE {OA} DROP CONSTRAINT ck_ownership_assignment_role")
    op.execute(
        f"ALTER TABLE {OA} ADD CONSTRAINT ck_ownership_assignment_role "
        "CHECK (role IN ('primary', 'co_owner', 'backup', 'temporary'))"
    )
    op.execute(
        f"ALTER TABLE {OA} ADD CONSTRAINT ck_ownership_assignment_temporary_bounded "
        "CHECK (role <> 'temporary' OR valid_to IS NOT NULL)"
    )
    op.execute(f"ALTER TABLE {OA} DROP CONSTRAINT ex_ownership_assignment_one_role")
    op.execute(
        f"ALTER TABLE {OA} ADD CONSTRAINT ex_ownership_assignment_one_role "
        "EXCLUDE USING gist (tenant_id WITH =, responsibility_id WITH =, "
        f"(COALESCE(person_id, team_id)) WITH =, {PERIOD} WITH &&) WHERE (role <> 'temporary')"
    )
    op.execute(
        f"ALTER TABLE {OA} ADD CONSTRAINT ex_ownership_assignment_one_temporary "
        f"EXCLUDE USING gist (tenant_id WITH =, responsibility_id WITH =, {PERIOD} WITH &&) "
        "WHERE (role = 'temporary')"
    )
    change = "catalog.ownership_assignment_change"
    op.execute(
        f"ALTER TABLE {change} ADD CONSTRAINT ck_ownership_assignment_change_change_type "
        "CHECK (change_type IN ('assigned', 'ended', 'extended'))"
    )

    # ---- identity: member display profile (self-reported, display only)
    op.add_column("membership", sa.Column("display_name", sa.Text()), schema="identity")
    op.add_column("membership", sa.Column("email", sa.Text()), schema="identity")

    # ---- continuity cases
    op.execute("CREATE SCHEMA continuity")
    op.execute(f"GRANT USAGE ON SCHEMA continuity TO {role}")

    op.create_table(
        "continuity_case",
        *_base("continuity_case"),
        sa.Column("case_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("status", sa.Text(), server_default="draft", nullable=False),
        sa.Column("outcome", sa.Text()),
        sa.Column("affected_person_id", sa.Uuid()),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True)),
        sa.Column("plan_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("initiator_user_id", sa.Uuid(), nullable=False),
        sa.Column("coordinator_user_id", sa.Uuid(), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
        _ts("closed_at", nullable=True),
        _fk(["affected_person_id"], "directory.person.id", "fk_case_affected_person"),
        _user_fk("continuity_case", "initiator_user_id"),
        _user_fk("continuity_case", "coordinator_user_id"),
        sa.CheckConstraint(
            "case_type IN ('transfer', 'coverage', 'departure')",
            name=op.f("ck_continuity_case_case_type"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'planning', 'executing', 'completed', 'cancelled')",
            name=op.f("ck_continuity_case_status"),
        ),
        sa.CheckConstraint(
            "outcome IS NULL OR outcome IN ('completed', 'completed_with_exceptions', 'cancelled')",
            name=op.f("ck_continuity_case_outcome"),
        ),
        sa.CheckConstraint(
            "char_length(title) BETWEEN 1 AND 200", name=op.f("ck_continuity_case_title_length")
        ),
        sa.CheckConstraint(
            "(case_type = 'coverage') = (ends_at IS NOT NULL)",
            name=op.f("ck_continuity_case_coverage_end"),
        ),
        sa.CheckConstraint(
            "ends_at IS NULL OR ends_at > starts_at", name=op.f("ck_continuity_case_range")
        ),
        sa.CheckConstraint(
            "case_type = 'transfer' OR affected_person_id IS NOT NULL",
            name=op.f("ck_continuity_case_affected_person"),
        ),
        schema="continuity",
    )
    op.create_index(
        "ix_continuity_case_tenant_id_status",
        "continuity_case",
        ["tenant_id", "status"],
        schema="continuity",
    )

    op.create_table(
        "case_scope_item",
        *_base("case_scope_item"),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("responsibility_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("current_assignment_id", sa.Uuid()),
        sa.Column("recipient_person_id", sa.Uuid()),
        sa.Column("recipient_team_id", sa.Uuid()),
        sa.Column("handover_notes", sa.Text()),
        sa.Column("exception_reason", sa.Text()),
        sa.Column("state", sa.Text(), server_default="planned", nullable=False),
        sa.Column("applied_assignment_id", sa.Uuid()),
        _ts("created_at"),
        _fk(["case_id"], "continuity.continuity_case.id", "fk_scope_item_case"),
        _fk(["responsibility_id"], "catalog.responsibility.id", "fk_scope_item_responsibility"),
        _fk(
            ["current_assignment_id"],
            "catalog.ownership_assignment.id",
            "fk_scope_item_current_assignment",
        ),
        _fk(
            ["applied_assignment_id"],
            "catalog.ownership_assignment.id",
            "fk_scope_item_applied_assignment",
        ),
        _fk(["recipient_person_id"], "directory.person.id", "fk_scope_item_recipient_person"),
        _fk(["recipient_team_id"], "directory.team.id", "fk_scope_item_recipient_team"),
        sa.UniqueConstraint(
            "tenant_id", "case_id", "responsibility_id", name="uq_scope_item_case_responsibility"
        ),
        sa.CheckConstraint(
            "role IN ('primary', 'co_owner', 'backup')", name=op.f("ck_case_scope_item_role")
        ),
        sa.CheckConstraint(
            "state IN ('planned', 'applied', 'excepted')", name=op.f("ck_case_scope_item_state")
        ),
        sa.CheckConstraint(
            "num_nonnulls(recipient_person_id, recipient_team_id) <= 1",
            name=op.f("ck_case_scope_item_one_recipient"),
        ),
        schema="continuity",
    )

    op.create_table(
        "case_task",
        *_base("case_task"),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("scope_item_id", sa.Uuid()),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("assignee_user_id", sa.Uuid()),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.Text(), server_default="open", nullable=False),
        sa.Column("completed_by", sa.Uuid()),
        _ts("completed_at", nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        _ts("created_at"),
        _fk(["case_id"], "continuity.continuity_case.id", "fk_case_task_case"),
        _fk(["scope_item_id"], "continuity.case_scope_item.id", "fk_case_task_scope_item"),
        _user_fk("case_task", "assignee_user_id"),
        _user_fk("case_task", "completed_by"),
        _user_fk("case_task", "created_by"),
        sa.CheckConstraint(
            "status IN ('open', 'done', 'cancelled')", name=op.f("ck_case_task_status")
        ),
        sa.CheckConstraint(
            "char_length(title) BETWEEN 1 AND 200", name=op.f("ck_case_task_title_length")
        ),
        schema="continuity",
    )
    op.create_index(
        "ix_case_task_tenant_id_assignee_user_id",
        "case_task",
        ["tenant_id", "assignee_user_id"],
        schema="continuity",
    )

    op.create_table(
        "case_readiness_criterion",
        *_base("case_readiness_criterion"),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("scope_item_id", sa.Uuid()),
        sa.Column("criterion_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("mandatory", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("resolved_by", sa.Uuid()),
        _ts("resolved_at", nullable=True),
        _ts("created_at"),
        _fk(["case_id"], "continuity.continuity_case.id", "fk_criterion_case"),
        _fk(["scope_item_id"], "continuity.case_scope_item.id", "fk_criterion_scope_item"),
        _user_fk("case_readiness_criterion", "resolved_by"),
        sa.CheckConstraint(
            "criterion_type IN ('attestation', 'task_completed', 'artefact_linked', "
            "'supervised_demo', 'access_confirmed', 'qa_reviewed')",
            name=op.f("ck_case_readiness_criterion_type"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'met', 'blocked', 'waived')",
            name=op.f("ck_case_readiness_criterion_status"),
        ),
        sa.CheckConstraint(
            "status <> 'waived' OR note IS NOT NULL",
            name=op.f("ck_case_readiness_criterion_waiver"),
        ),
        schema="continuity",
    )

    op.create_table(
        "case_approval",
        *_base("case_approval"),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("plan_version", sa.Integer(), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column("sod_exception_reason", sa.Text()),
        sa.Column("approver_user_id", sa.Uuid(), nullable=False),
        _ts("decided_at"),
        _fk(["case_id"], "continuity.continuity_case.id", "fk_case_approval_case"),
        _user_fk("case_approval", "approver_user_id"),
        sa.CheckConstraint(
            "decision IN ('approved', 'rejected')", name=op.f("ck_case_approval_decision")
        ),
        schema="continuity",
    )

    for table, privileges in (
        ("continuity_case", ["SELECT", "INSERT", "UPDATE"]),
        ("case_scope_item", ["SELECT", "INSERT", "UPDATE", "DELETE"]),
        ("case_task", ["SELECT", "INSERT", "UPDATE"]),
        ("case_readiness_criterion", ["SELECT", "INSERT", "UPDATE", "DELETE"]),
        ("case_approval", ["SELECT", "INSERT"]),  # decisions are never edited
    ):
        enable_tenant_rls("continuity", table)
        grant_table("continuity", table, role, privileges)


def downgrade() -> None:
    for table in (
        "case_approval",
        "case_readiness_criterion",
        "case_task",
        "case_scope_item",
        "continuity_case",
    ):
        op.drop_table(table, schema="continuity")
    op.execute("DROP SCHEMA continuity")
    op.drop_column("membership", "email", schema="identity")
    op.drop_column("membership", "display_name", schema="identity")
    change = "catalog.ownership_assignment_change"
    op.execute(
        f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM {OA} WHERE role = 'temporary') THEN "
        "RAISE EXCEPTION 'temporary coverage assignments exist; cannot downgrade'; END IF; END $$"
    )
    op.execute(f"ALTER TABLE {change} DROP CONSTRAINT ck_ownership_assignment_change_change_type")
    op.execute(
        f"ALTER TABLE {change} ADD CONSTRAINT ck_ownership_assignment_change_change_type "
        "CHECK (change_type IN ('assigned', 'ended'))"
    )
    op.execute(f"ALTER TABLE {OA} DROP CONSTRAINT ex_ownership_assignment_one_temporary")
    op.execute(f"ALTER TABLE {OA} DROP CONSTRAINT ex_ownership_assignment_one_role")
    op.execute(
        f"ALTER TABLE {OA} ADD CONSTRAINT ex_ownership_assignment_one_role "
        "EXCLUDE USING gist (tenant_id WITH =, responsibility_id WITH =, "
        f"(COALESCE(person_id, team_id)) WITH =, {PERIOD} WITH &&)"
    )
    op.execute(f"ALTER TABLE {OA} DROP CONSTRAINT ck_ownership_assignment_temporary_bounded")
    op.execute(f"ALTER TABLE {OA} DROP CONSTRAINT ck_ownership_assignment_role")
    op.execute(
        f"ALTER TABLE {OA} ADD CONSTRAINT ck_ownership_assignment_role "
        "CHECK (role IN ('primary', 'co_owner', 'backup'))"
    )
