"""indexes for the lookups the services run on every request

Each of these filters on a column that no index led with (after `tenant_id`), so the query
scanned the whole table for its workspace. All are plain additive indexes (expand-only; no
code change depends on them being present, they only make existing queries cheaper):

- continuity.case_scope_item (responsibility_id)
- continuity.case_readiness_criterion (scope_item_id)
- continuity.case_knowledge (recorded_at)
- catalog.ownership_assignment (person_id)
- integrations.linear_project (responsibility_id)
- integrations.notion_source (responsibility_id)
- integrations.github_repository (responsibility_id)
- governance.connector_run (finished_at)
- intelligence.proposal (reviewed_at)
- intelligence.agent_run (created_at)
- audit.audit_event (actor_user_id)
- directory.team_member (person_id)

Revision ID: 0042
Revises: 0041
Create Date: 2026-11-15
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0042"
down_revision: str | None = "0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (schema, table, column, index name). Names follow the project's naming convention
# (ix_<table>_<columns>), which the model-drift test compares against.
INDEXES = [
    (
        "continuity",
        "case_scope_item",
        "responsibility_id",
        "ix_case_scope_item_tenant_id_responsibility_id",
    ),
    (
        "continuity",
        "case_readiness_criterion",
        "scope_item_id",
        "ix_case_readiness_criterion_tenant_id_scope_item_id",
    ),
    ("continuity", "case_knowledge", "recorded_at", "ix_case_knowledge_tenant_id_recorded_at"),
    ("catalog", "ownership_assignment", "person_id", "ix_ownership_assignment_tenant_id_person_id"),
    (
        "integrations",
        "linear_project",
        "responsibility_id",
        "ix_linear_project_tenant_id_responsibility_id",
    ),
    (
        "integrations",
        "notion_source",
        "responsibility_id",
        "ix_notion_source_tenant_id_responsibility_id",
    ),
    (
        "integrations",
        "github_repository",
        "responsibility_id",
        "ix_github_repository_tenant_id_responsibility_id",
    ),
    ("governance", "connector_run", "finished_at", "ix_connector_run_tenant_id_finished_at"),
    ("intelligence", "proposal", "reviewed_at", "ix_proposal_tenant_id_reviewed_at"),
    ("intelligence", "agent_run", "created_at", "ix_agent_run_tenant_id_created_at"),
    ("audit", "audit_event", "actor_user_id", "ix_audit_event_tenant_id_actor_user_id"),
    ("directory", "team_member", "person_id", "ix_team_member_tenant_id_person_id"),
]


def upgrade() -> None:
    for schema, table, column, name in INDEXES:
        op.create_index(name, table, ["tenant_id", column], schema=schema)


def downgrade() -> None:
    for schema, table, _column, name in reversed(INDEXES):
        op.drop_index(name, table, schema=schema)
