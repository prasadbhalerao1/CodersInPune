"""retention policy and data classification

- governance.workspace_policy.retention_days: how long operational records are kept
  (read notifications, connector run history, AI run step events). Audit events are
  never purged by retention; they are the record of what happened.
- catalog.knowledge_item.classification: public, internal, confidential or restricted.
  Confidential and restricted knowledge is managers-only (enforced by a check).
- DELETE grants for the retention job on the operational tables it purges.

Revision ID: 0033
Revises: 0032
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from relay.shared.db.migration_ops import app_role, grant_table

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PURGED = (
    ("notifications", "notification"),
    ("governance", "connector_run"),
    ("intelligence", "agent_run_event"),
)


def upgrade() -> None:
    for schema, table in PURGED:
        grant_table(schema, table, app_role(), ["DELETE"])
    op.add_column(
        "workspace_policy",
        sa.Column("retention_days", sa.Integer(), server_default="365", nullable=False),
        schema="governance",
    )
    op.create_check_constraint(
        op.f("ck_workspace_policy_retention_days"),
        "workspace_policy",
        "retention_days BETWEEN 30 AND 3650",
        schema="governance",
    )
    op.add_column(
        "knowledge_item",
        sa.Column("classification", sa.Text(), server_default="internal", nullable=False),
        schema="catalog",
    )
    op.create_check_constraint(
        op.f("ck_knowledge_item_classification"),
        "knowledge_item",
        "classification IN ('public', 'internal', 'confidential', 'restricted')",
        schema="catalog",
    )
    op.create_check_constraint(
        op.f("ck_knowledge_item_classified_visibility"),
        "knowledge_item",
        "classification NOT IN ('confidential', 'restricted') OR visibility = 'managers'",
        schema="catalog",
    )


def downgrade() -> None:
    for schema, table in PURGED:
        op.execute(f"REVOKE DELETE ON {schema}.{table} FROM {app_role()}")
    op.drop_constraint(
        "ck_knowledge_item_classified_visibility", "knowledge_item", schema="catalog"
    )
    op.drop_constraint("ck_knowledge_item_classification", "knowledge_item", schema="catalog")
    op.drop_column("knowledge_item", "classification", schema="catalog")
    op.drop_constraint(
        "ck_workspace_policy_retention_days", "workspace_policy", schema="governance"
    )
    op.drop_column("workspace_policy", "retention_days", schema="governance")
