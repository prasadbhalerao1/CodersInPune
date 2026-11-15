"""operational summary: aggregate health counts for alerting (NFR-OBS-A01)

`platform.ops_summary()` returns counts only (no identifiers, names or content) across all
workspaces: worker heartbeat age, queue depth, failed jobs, failing outbox events,
unhealthy connectors, failed emails and failed AI runs. It is SECURITY DEFINER and runs as
the owner; tenant tables keep FORCE RLS, so each read table gets an `ops_read` SELECT
policy for the owner that matches only while the function has set `app.ops` (the app role
is never the owner, so it can't use these policies). The app role may execute it; the
API exposes it only behind an operator token.

Revision ID: 0039
Revises: 0038
Create Date: 2026-11-10
"""

from collections.abc import Sequence

from alembic import op

from relay.shared.db.migration_ops import app_role

revision: str = "0039"
down_revision: str | None = "0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

READ = (
    "integrations.github_installation",
    "integrations.linear_connection",
    "integrations.notion_connection",
    "notifications.email_delivery",
    "intelligence.agent_run",
    "platform.outbox_event",
)


def upgrade() -> None:
    for table in READ:
        op.execute(
            f"CREATE POLICY ops_read ON {table} FOR SELECT TO CURRENT_USER "
            "USING (current_setting('app.ops', true) = 'on')"
        )
    op.execute(
        """
        CREATE FUNCTION platform.ops_summary() RETURNS jsonb
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
        DECLARE
            result jsonb;
        BEGIN
            PERFORM set_config('app.ops', 'on', true);
            SELECT jsonb_build_object(
                'worker_heartbeat_age_s', (
                    SELECT extract(epoch FROM clock_timestamp() - max(last_heartbeat))::integer
                    FROM public.procrastinate_workers),
                'queue_ready', (
                    SELECT count(*) FROM public.procrastinate_jobs
                    WHERE status = 'todo'
                      AND (scheduled_at IS NULL OR scheduled_at <= clock_timestamp())),
                'oldest_ready_age_s', (
                    SELECT extract(epoch FROM clock_timestamp() - min(e.at))::integer
                    FROM public.procrastinate_jobs j
                    JOIN public.procrastinate_events e ON e.job_id = j.id AND e.type = 'deferred'
                    WHERE j.status = 'todo'
                      AND (j.scheduled_at IS NULL OR j.scheduled_at <= clock_timestamp())),
                'jobs_failed_1h', (
                    SELECT count(*) FROM public.procrastinate_events
                    WHERE type = 'failed' AND at > clock_timestamp() - interval '1 hour'),
                'events_failing', (
                    SELECT count(*) FROM platform.outbox_event
                    WHERE processed_at IS NULL AND last_error_type IS NOT NULL),
                'connectors_unhealthy', (
                    SELECT count(*) FROM (
                        SELECT status, last_sync_status, paused
                        FROM integrations.github_installation
                        UNION ALL
                        SELECT status, last_sync_status, paused FROM integrations.linear_connection
                        UNION ALL
                        SELECT status, last_sync_status, paused FROM integrations.notion_connection
                    ) c
                    WHERE NOT c.paused
                      AND (c.status = 'revoked' OR c.last_sync_status = 'failed')),
                'emails_failed_24h', (
                    SELECT count(*) FROM notifications.email_delivery
                    WHERE status = 'failed' AND updated_at > clock_timestamp() - interval '1 day'),
                'ai_runs_failed_24h', (
                    SELECT count(*) FROM intelligence.agent_run
                    WHERE state IN ('failed', 'timed_out')
                      AND created_at > clock_timestamp() - interval '1 day'),
                'ai_budget_exhausted_24h', (
                    SELECT count(*) FROM intelligence.agent_run
                    WHERE error_code LIKE '%budget%'
                      AND created_at > clock_timestamp() - interval '1 day')
            ) INTO result;
            PERFORM set_config('app.ops', '', true);
            RETURN result;
        END $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION platform.ops_summary() FROM PUBLIC")
    op.execute(f'GRANT EXECUTE ON FUNCTION platform.ops_summary() TO "{app_role()}"')


def downgrade() -> None:
    op.execute("DROP FUNCTION platform.ops_summary()")
    for table in READ:
        op.execute(f"DROP POLICY ops_read ON {table}")
