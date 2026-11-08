"""procrastinate 3.10.0 job queue schema

Procrastinate's tables live in `public` (where its SQL expects them) and are not
tenant-scoped: a job row carries only (tenant_id, event_id). The worker re-establishes the
tenant context before touching tenant data, and tenant data stays in the RLS-protected
outbox. The application role gets DML on Procrastinate's objects only.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-08
"""

from collections.abc import Sequence
from pathlib import Path

from alembic import op

from relay.shared.db.migration_ops import app_role

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA_SQL = Path(__file__).parents[1] / "sql" / "procrastinate_3_10_0_schema.sql"
TABLES = (
    "procrastinate_workers",
    "procrastinate_jobs",
    "procrastinate_periodic_defers",
    "procrastinate_events",
)


def upgrade() -> None:
    role = app_role()
    # Raw driver execution: the SQL contains '%' in PL/pgSQL RAISE strings, which must not
    # be treated as bind-parameter markers.
    raw = op.get_bind().connection.dbapi_connection
    assert raw is not None
    raw.cursor().execute(SCHEMA_SQL.read_text(encoding="utf-8"))
    for table in TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON public.{table} TO {role}")
    op.execute(
        f"""
        DO $$ DECLARE s record; BEGIN
            FOR s IN SELECT sequence_name FROM information_schema.sequences
                     WHERE sequence_schema = 'public' AND sequence_name LIKE 'procrastinate_%'
            LOOP
                EXECUTE format(
                    'GRANT USAGE, SELECT ON SEQUENCE public.%I TO {role}', s.sequence_name
                );
            END LOOP;
        END $$
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$ DECLARE r record; BEGIN
            FOR r IN SELECT p.oid::regprocedure AS sig FROM pg_proc p
                     JOIN pg_namespace n ON n.oid = p.pronamespace
                     WHERE n.nspname = 'public' AND p.proname LIKE 'procrastinate_%'
            LOOP EXECUTE format('DROP FUNCTION %s CASCADE', r.sig); END LOOP;
        END $$
        """
    )
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE IF EXISTS public.{table} CASCADE")
    for type_name in (
        "procrastinate_job_to_defer_v1",
        "procrastinate_job_event_type",
        "procrastinate_job_status",
    ):
        op.execute(f"DROP TYPE IF EXISTS public.{type_name} CASCADE")
