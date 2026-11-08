import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import psycopg
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from relay.config import Settings
from relay.shared.db import create_engine, create_session_factory
from tests.db import APP_ROLE, APP_URL, OWNER_URL, libpq_url
from tests.tokens import CLIENT_ID

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def anyio_backend() -> tuple[str, dict[str, Any]]:
    # psycopg async needs a selector loop on Windows (see relay/__main__.py).
    options: dict[str, Any] = {}
    if sys.platform == "win32":
        options["loop_factory"] = asyncio.SelectorEventLoop
    return ("asyncio", options)


def _truncate_all_tables() -> None:
    """Empty every table left by a previous run so the downgrade/upgrade cycle starts clean."""
    with psycopg.connect(libpq_url(OWNER_URL), autocommit=True) as conn:
        tables = conn.execute(
            "SELECT format('%I.%I', schemaname, tablename) FROM pg_tables "
            "WHERE tableowner = current_user AND tablename <> 'alembic_version'"
        ).fetchall()
        if tables:
            conn.execute(f"TRUNCATE {', '.join(t[0] for t in tables)} CASCADE")


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    """Rebuild the test schema from migrations: proves downgrade and upgrade both work."""
    _truncate_all_tables()
    env = {**os.environ, "RELAY_MIGRATION_DATABASE_URL": OWNER_URL, "RELAY_APP_DB_ROLE": APP_ROLE}
    for args in (["downgrade", "base"], ["upgrade", "head"]):
        result = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [sys.executable, "-m", "alembic", *args],
            cwd=BACKEND_DIR,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            pytest.fail(
                f"alembic {' '.join(args)} failed. Is Postgres running "
                f"(`docker compose up -d --wait`)?\n{result.stderr}",
                pytrace=False,
            )


@pytest.fixture(autouse=True)
def clean_tables() -> None:
    with psycopg.connect(libpq_url(OWNER_URL), autocommit=True) as conn:
        conn.execute(
            "TRUNCATE continuity.case_approval, continuity.case_readiness_criterion, "
            "continuity.case_task, continuity.case_scope_item, continuity.continuity_case, "
            "catalog.ownership_assignment_change, catalog.ownership_assignment, "
            "catalog.responsibility, directory.team_member, directory.team, directory.person, "
            "public.procrastinate_events, public.procrastinate_jobs, "
            "public.procrastinate_periodic_defers, public.procrastinate_workers, "
            "audit.audit_event, platform.outbox_event, "
            "identity.workspace_creation_request, identity.membership, "
            "identity.user_account, platform.tenant_probe_item, platform.tenant_probe, "
            "platform.tenant CASCADE"
        )


def make_settings(**overrides: Any) -> Settings:
    defaults: dict[str, Any] = {
        "database_url": APP_URL,
        "environment": "test",
        "workos_client_id": CLIENT_ID,
    }
    return Settings(**{**defaults, **overrides})


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
async def engine(settings: Settings) -> AsyncIterator[AsyncEngine]:
    eng = create_engine(settings)
    yield eng
    await eng.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(engine)
