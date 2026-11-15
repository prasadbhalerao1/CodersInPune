"""guidance state: per-member product guidance switch, tutorial progress and dismissals

`identity.guidance_state` holds one row per member who changed anything: whether
automatic guidance is on, which tours are finished or tips dismissed, and the step an
interrupted tour stopped at. Tour ids only; never user content.

Revision ID: 0041
Revises: 0040
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from relay.shared.db.migration_ops import app_role, enable_tenant_rls, grant_table

revision: str = "0041"
down_revision: str | None = "0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

S = "identity"
T = "guidance_state"


def upgrade() -> None:
    op.create_table(
        T,
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("completed", JSONB(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("dismissed", JSONB(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("progress", JSONB(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=f"pk_{T}"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["platform.tenant.id"], name=f"fk_{T}_tenant_id_tenant"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["identity.user_account.id"], name=f"fk_{T}_user_id_user_account"
        ),
        sa.UniqueConstraint("tenant_id", "id", name=f"uq_{T}_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "user_id", name=f"uq_{T}_tenant_id_user_id"),
        schema=S,
    )
    enable_tenant_rls(S, T)
    grant_table(S, T, app_role(), ["SELECT", "INSERT", "UPDATE"])


def downgrade() -> None:
    op.drop_table(T, schema=S)
