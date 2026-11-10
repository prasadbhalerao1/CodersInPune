"""responsibility, asset and risk governance

Responsibilities
- restricted (fail-closed): a RESTRICTIVE row policy hides restricted responsibilities
  from every query (lists, counts, search, joins) unless the caller is an owner/admin of
  the workspace, was granted access (responsibility_access), currently holds it (person
  matched to the member by email), or the session has no principal (background jobs act
  for the workspace). The service layer applies the same rule (defence in depth).
- managed types (responsibility_type) instead of free-text categories (category is kept,
  expand only); escalation path/contact; review cadence and last review; needs-human-
  verification flag; required procedures and access prerequisites; accountable contact
  (a person) for team-owned critical responsibilities.
- responsibility_dependency: depends on another responsibility or an asset, with the
  relationship type and provenance (who/what recorded it).
- ownership_assignment_change: change type `corrected` for backdated corrections.

Governance
- criticality_policy: per criticality tier: backup required, review cadence, accountable
  contact required for team-owned responsibilities.

Assets
- criticality, tags, lifecycle, external source + id, typed metadata, source state
  (available/unavailable); types customer_account and infrastructure.
- asset_link: links an asset to knowledge, a case or a task.

Risks
- dispositions in_remediation and dismissed (dismissal needs a reason).

Revision ID: 0025
Revises: 0024
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from relay.shared.db.migration_ops import app_role, enable_tenant_rls, grant_table

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CAT = "catalog"
RESP = "responsibility"
OLD_ASSET_TYPES = (
    "repository",
    "service",
    "project",
    "process",
    "vendor",
    "document_collection",
    "other",
)
ASSET_TYPES = (*OLD_ASSET_TYPES, "customer_account", "infrastructure")


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


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
    return sa.ForeignKeyConstraint(
        ["tenant_id", *cols], [f"{target}.tenant_id", f"{target}.id"], name=name
    )


def _user(table: str, column: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["identity.user_account.id"], name=f"fk_{table}_{column}_user_account"
    )


def _ts(name: str, nullable: bool = False) -> sa.Column[sa.DateTime]:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=None if nullable else sa.func.now(),
        nullable=nullable,
    )


def _check(table: str, name: str, condition: str, schema: str = CAT) -> None:
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, condition, schema=schema)


def _replace_check(table: str, name: str, condition: str, schema: str = CAT) -> None:
    op.drop_constraint(f"ck_{table}_{name}", table, schema=schema)
    _check(table, name, condition, schema)


def upgrade() -> None:
    role = app_role()
    add = op.add_column

    t = "responsibility_type"
    op.create_table(
        t,
        *_base(t),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("review_cadence_days", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        _ts("created_at"),
        _user(t, "created_by"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_responsibility_type_tenant_id_name"),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 80", name=op.f(f"ck_{t}_name_length")),
        sa.CheckConstraint(
            "review_cadence_days IS NULL OR review_cadence_days BETWEEN 7 AND 730",
            name=op.f(f"ck_{t}_review_cadence_days"),
        ),
        schema=CAT,
    )

    add(
        RESP,
        sa.Column("restricted", sa.Boolean(), server_default=sa.false(), nullable=False),
        schema=CAT,
    )
    add(RESP, sa.Column("type_id", sa.Uuid(), nullable=True), schema=CAT)
    add(RESP, sa.Column("escalation_path", sa.Text(), nullable=True), schema=CAT)
    add(RESP, sa.Column("escalation_contact", sa.Text(), nullable=True), schema=CAT)
    add(RESP, sa.Column("review_cadence_days", sa.Integer(), nullable=True), schema=CAT)
    add(RESP, _ts("last_reviewed_at", nullable=True), schema=CAT)
    add(RESP, sa.Column("last_reviewed_by", sa.Uuid(), nullable=True), schema=CAT)
    add(
        RESP,
        sa.Column("needs_verification", sa.Boolean(), server_default=sa.false(), nullable=False),
        schema=CAT,
    )
    add(
        RESP,
        sa.Column("procedures", JSONB(), server_default=sa.text("'[]'"), nullable=False),
        schema=CAT,
    )
    add(
        RESP,
        sa.Column("access_prerequisites", JSONB(), server_default=sa.text("'[]'"), nullable=False),
        schema=CAT,
    )
    add(RESP, sa.Column("accountable_person_id", sa.Uuid(), nullable=True), schema=CAT)
    op.create_foreign_key(
        "fk_responsibility_type",
        RESP,
        "responsibility_type",
        ["tenant_id", "type_id"],
        ["tenant_id", "id"],
        source_schema=CAT,
        referent_schema=CAT,
    )
    op.create_foreign_key(
        "fk_responsibility_accountable_person",
        RESP,
        "person",
        ["tenant_id", "accountable_person_id"],
        ["tenant_id", "id"],
        source_schema=CAT,
        referent_schema="directory",
    )
    op.create_foreign_key(
        "fk_responsibility_last_reviewed_by_user_account",
        RESP,
        "user_account",
        ["last_reviewed_by"],
        ["id"],
        source_schema=CAT,
        referent_schema="identity",
    )
    _check(
        RESP,
        "review_cadence_days",
        "review_cadence_days IS NULL OR review_cadence_days BETWEEN 7 AND 730",
    )

    t = "responsibility_access"
    op.create_table(
        t,
        *_base(t),
        sa.Column("responsibility_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("granted_by", sa.Uuid(), nullable=False),
        _ts("granted_at"),
        _fk(
            ["responsibility_id"],
            "catalog.responsibility",
            "fk_responsibility_access_responsibility",
        ),
        _user(t, "user_id"),
        _user(t, "granted_by"),
        sa.UniqueConstraint(
            "tenant_id",
            "responsibility_id",
            "user_id",
            name="uq_responsibility_access_tenant_id_responsibility_id_user_id",
        ),
        schema=CAT,
    )

    t = "responsibility_dependency"
    op.create_table(
        t,
        *_base(t),
        sa.Column("responsibility_id", sa.Uuid(), nullable=False),
        sa.Column("depends_on_responsibility_id", sa.Uuid(), nullable=True),
        sa.Column("depends_on_asset_id", sa.Uuid(), nullable=True),
        sa.Column("relationship", sa.Text(), nullable=False),
        sa.Column("provenance", sa.Text(), server_default="manual", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        _ts("created_at"),
        _fk(
            ["responsibility_id"],
            "catalog.responsibility",
            "fk_responsibility_dependency_responsibility",
        ),
        _fk(
            ["depends_on_responsibility_id"],
            "catalog.responsibility",
            "fk_responsibility_dependency_target",
        ),
        _fk(["depends_on_asset_id"], "catalog.asset", "fk_responsibility_dependency_asset"),
        _user(t, "created_by"),
        sa.CheckConstraint(
            "num_nonnulls(depends_on_responsibility_id, depends_on_asset_id) = 1",
            name=op.f(f"ck_{t}_one_target"),
        ),
        sa.CheckConstraint(
            "depends_on_responsibility_id IS NULL "
            "OR depends_on_responsibility_id <> responsibility_id",
            name=op.f(f"ck_{t}_not_self"),
        ),
        sa.CheckConstraint(
            _in("relationship", ("depends_on", "feeds", "escalates_to", "shares_access")),
            name=op.f(f"ck_{t}_relationship"),
        ),
        sa.CheckConstraint(
            _in("provenance", ("manual", "github", "linear", "notion", "import", "ai_accepted")),
            name=op.f(f"ck_{t}_provenance"),
        ),
        schema=CAT,
    )
    op.create_index(
        f"ix_{t}_tenant_id_responsibility_id", t, ["tenant_id", "responsibility_id"], schema=CAT
    )

    # Fail-closed visibility of restricted responsibilities, in the database itself.
    op.execute(
        """
        CREATE FUNCTION catalog.can_see_responsibility(is_restricted boolean, rid uuid)
        RETURNS boolean LANGUAGE sql STABLE PARALLEL SAFE
        AS $$
          SELECT NOT is_restricted
            OR identity.current_principal() IS NULL
            OR EXISTS (
              SELECT 1 FROM identity.membership m
              WHERE m.user_id = identity.current_user_id()
                AND m.tenant_id = platform.current_tenant_id()
                AND m.status = 'active' AND m.role IN ('owner', 'admin'))
            OR EXISTS (
              SELECT 1 FROM catalog.responsibility_access a
              WHERE a.responsibility_id = rid AND a.user_id = identity.current_user_id())
            OR EXISTS (
              SELECT 1 FROM catalog.ownership_assignment oa
              JOIN directory.person p ON p.id = oa.person_id
              JOIN identity.membership m
                ON lower(m.email) = lower(p.email) AND m.tenant_id = p.tenant_id
              WHERE oa.responsibility_id = rid
                AND m.user_id = identity.current_user_id() AND m.status = 'active'
                AND oa.valid_from <= now() AND (oa.valid_to IS NULL OR oa.valid_to > now()))
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION catalog.can_see_responsibility(boolean, uuid) FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION catalog.can_see_responsibility(boolean, uuid) TO {role}")
    op.execute(
        "CREATE POLICY restricted_visibility ON catalog.responsibility AS RESTRICTIVE "
        "USING (catalog.can_see_responsibility(restricted, id)) "
        "WITH CHECK (catalog.can_see_responsibility(restricted, id))"
    )

    op.drop_constraint(
        "ck_ownership_assignment_change_change_type", "ownership_assignment_change", schema=CAT
    )
    op.execute(
        "ALTER TABLE catalog.ownership_assignment_change ADD CONSTRAINT "
        "ck_ownership_assignment_change_change_type "
        "CHECK (change_type IN ('assigned', 'ended', 'extended', 'corrected'))"
    )

    t = "criticality_policy"
    op.create_table(
        t,
        *_base(t),
        sa.Column("criticality", sa.Text(), nullable=False),
        sa.Column("requires_backup", sa.Boolean(), nullable=False),
        sa.Column("review_days", sa.Integer(), nullable=False),
        sa.Column("requires_accountable_contact", sa.Boolean(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        _ts("updated_at"),
        _user(t, "updated_by"),
        sa.UniqueConstraint(
            "tenant_id", "criticality", name="uq_criticality_policy_tenant_id_criticality"
        ),
        sa.CheckConstraint(
            _in("criticality", ("critical", "high", "standard", "low")),
            name=op.f(f"ck_{t}_criticality"),
        ),
        sa.CheckConstraint("review_days BETWEEN 7 AND 730", name=op.f(f"ck_{t}_review_days")),
        schema="governance",
    )

    asset = "asset"
    add(asset, sa.Column("criticality", sa.Text(), nullable=True), schema=CAT)
    add(
        asset,
        sa.Column("tags", ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False),
        schema=CAT,
    )
    add(
        asset,
        sa.Column("lifecycle", sa.Text(), server_default="active", nullable=False),
        schema=CAT,
    )
    add(asset, sa.Column("external_source", sa.Text(), nullable=True), schema=CAT)
    add(asset, sa.Column("external_id", sa.Text(), nullable=True), schema=CAT)
    add(
        asset,
        sa.Column("metadata", JSONB(), server_default=sa.text("'{}'"), nullable=False),
        schema=CAT,
    )
    add(
        asset,
        sa.Column("source_state", sa.Text(), server_default="available", nullable=False),
        schema=CAT,
    )
    _replace_check(asset, "asset_type", _in("asset_type", ASSET_TYPES))
    _check(
        asset,
        "criticality",
        "criticality IS NULL OR criticality IN ('critical', 'high', 'standard', 'low')",
    )
    _check(asset, "lifecycle", _in("lifecycle", ("planned", "active", "deprecated", "retired")))
    _check(
        asset,
        "external_source",
        "external_source IS NULL OR external_source IN ('github', 'linear', 'notion', 'manual')",
    )
    _check(asset, "source_state", _in("source_state", ("available", "unavailable")))
    _check(asset, "tags", "cardinality(tags) <= 20")
    op.create_index("ix_asset_tags", asset, ["tags"], schema=CAT, postgresql_using="gin")

    t = "asset_link"
    op.create_table(
        t,
        *_base(t),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_item_id", sa.Uuid(), nullable=True),
        sa.Column("case_id", sa.Uuid(), nullable=True),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        _ts("created_at"),
        _fk(["asset_id"], "catalog.asset", "fk_asset_link_asset"),
        _fk(["knowledge_item_id"], "catalog.knowledge_item", "fk_asset_link_knowledge_item"),
        _fk(["case_id"], "continuity.continuity_case", "fk_asset_link_case"),
        _fk(["task_id"], "continuity.case_task", "fk_asset_link_task"),
        _user(t, "created_by"),
        sa.CheckConstraint(
            "num_nonnulls(knowledge_item_id, case_id, task_id) = 1", name=op.f(f"ck_{t}_one_target")
        ),
        schema=CAT,
    )
    op.create_index(f"ix_{t}_tenant_id_asset_id", t, ["tenant_id", "asset_id"], schema=CAT)

    risk = "risk_record"
    _replace_check(
        risk,
        "status",
        _in(
            "status",
            ("open", "acknowledged", "accepted", "resolved", "in_remediation", "dismissed"),
        ),
        schema="risks",
    )
    _check(risk, "dismissal", "status <> 'dismissed' OR note IS NOT NULL", schema="risks")

    for schema, table, grants in (
        (CAT, "responsibility_type", ["SELECT", "INSERT", "UPDATE"]),
        (CAT, "responsibility_access", ["SELECT", "INSERT", "DELETE"]),
        (CAT, "responsibility_dependency", ["SELECT", "INSERT", "DELETE"]),
        (CAT, "asset_link", ["SELECT", "INSERT", "DELETE"]),
        ("governance", "criticality_policy", ["SELECT", "INSERT", "UPDATE"]),
    ):
        enable_tenant_rls(schema, table)
        grant_table(schema, table, role, grants)


def downgrade() -> None:
    op.drop_constraint("ck_risk_record_dismissal", "risk_record", schema="risks")
    _replace_check(
        "risk_record",
        "status",
        _in("status", ("open", "acknowledged", "accepted", "resolved")),
        schema="risks",
    )
    op.drop_table("asset_link", schema=CAT)
    op.drop_index("ix_asset_tags", "asset", schema=CAT)
    for name in ("criticality", "lifecycle", "external_source", "source_state", "tags"):
        op.drop_constraint(f"ck_asset_{name}", "asset", schema=CAT)
    _replace_check("asset", "asset_type", _in("asset_type", OLD_ASSET_TYPES))
    for column in (
        "source_state",
        "metadata",
        "external_id",
        "external_source",
        "lifecycle",
        "tags",
        "criticality",
    ):
        op.drop_column("asset", column, schema=CAT)
    op.drop_table("criticality_policy", schema="governance")
    op.drop_constraint(
        "ck_ownership_assignment_change_change_type", "ownership_assignment_change", schema=CAT
    )
    op.execute(
        "ALTER TABLE catalog.ownership_assignment_change ADD CONSTRAINT "
        "ck_ownership_assignment_change_change_type "
        "CHECK (change_type IN ('assigned', 'ended', 'extended'))"
    )
    op.execute("DROP POLICY restricted_visibility ON catalog.responsibility")
    op.execute("DROP FUNCTION catalog.can_see_responsibility(boolean, uuid)")
    op.drop_table("responsibility_dependency", schema=CAT)
    op.drop_table("responsibility_access", schema=CAT)
    op.drop_constraint("ck_responsibility_review_cadence_days", RESP, schema=CAT)
    for name in (
        "fk_responsibility_last_reviewed_by_user_account",
        "fk_responsibility_accountable_person",
        "fk_responsibility_type",
    ):
        op.drop_constraint(name, RESP, schema=CAT)
    for column in (
        "accountable_person_id",
        "access_prerequisites",
        "procedures",
        "needs_verification",
        "last_reviewed_by",
        "last_reviewed_at",
        "review_cadence_days",
        "escalation_contact",
        "escalation_path",
        "type_id",
        "restricted",
    ):
        op.drop_column(RESP, column, schema=CAT)
    op.drop_table("responsibility_type", schema=CAT)
