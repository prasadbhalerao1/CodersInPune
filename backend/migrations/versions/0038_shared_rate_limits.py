"""shared rate limits: counters in PostgreSQL so every API replica enforces one limit

`platform.rate_limit_window` holds fixed-window hit counts per (bucket, user). The app role
has no privileges on it; it calls `platform.rate_limit_hit`, a SECURITY DEFINER function
that counts the hit atomically and returns the seconds to wait (0 = allowed). Windows
older than a day are pruned opportunistically.

Revision ID: 0038
Revises: 0037
Create Date: 2026-11-10
"""

from collections.abc import Sequence

from alembic import op

from relay.shared.db.migration_ops import app_role, enable_rls

revision: str = "0038"
down_revision: str | None = "0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE platform.rate_limit_window (
            bucket text NOT NULL,
            subject text NOT NULL,
            window_start timestamptz NOT NULL,
            hits integer NOT NULL,
            CONSTRAINT pk_rate_limit_window PRIMARY KEY (bucket, subject, window_start)
        )
        """
    )
    enable_rls("platform", "rate_limit_window")
    # Only the definer (the owner) touches the table; the app role has no grants on it.
    op.execute(
        "CREATE POLICY definer_only ON platform.rate_limit_window "
        "TO CURRENT_USER USING (true) WITH CHECK (true)"
    )
    op.execute(
        """
        CREATE FUNCTION platform.rate_limit_hit(
            p_bucket text, p_subject text, p_limit integer, p_window integer
        ) RETURNS integer
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
        DECLARE
            started timestamptz := to_timestamp(
                floor(extract(epoch FROM clock_timestamp()) / p_window) * p_window);
            n integer;
        BEGIN
            INSERT INTO platform.rate_limit_window AS w (bucket, subject, window_start, hits)
            VALUES (p_bucket, p_subject, started, 1)
            ON CONFLICT (bucket, subject, window_start) DO UPDATE SET hits = w.hits + 1
            RETURNING hits INTO n;
            IF random() < 0.01 THEN
                DELETE FROM platform.rate_limit_window
                WHERE window_start < clock_timestamp() - interval '1 day';
            END IF;
            IF n > p_limit THEN
                RETURN greatest(1, ceil(extract(epoch FROM
                    started + make_interval(secs => p_window) - clock_timestamp()))::integer);
            END IF;
            RETURN 0;
        END $$
        """
    )
    signature = "platform.rate_limit_hit(text, text, integer, integer)"
    op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
    op.execute(f'GRANT EXECUTE ON FUNCTION {signature} TO "{app_role()}"')


def downgrade() -> None:
    op.execute("DROP FUNCTION platform.rate_limit_hit(text, text, integer, integer)")
    op.execute("DROP TABLE platform.rate_limit_window")
