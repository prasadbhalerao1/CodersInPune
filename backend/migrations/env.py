"""Alembic environment. Runs as the owner role from RELAY_MIGRATION_DATABASE_URL."""

import asyncio
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine

# Register every model on Base.metadata (autogenerate comparisons).
import relay.audit.models  # noqa: F401
import relay.catalog.models  # noqa: F401
import relay.directory.models  # noqa: F401
import relay.identity.models  # noqa: F401
import relay.jobs.models  # noqa: F401
import relay.platform.models  # noqa: F401
from relay.config import MigrationSettings
from relay.shared.db.base import Base

MANAGED_SCHEMAS = {"platform", "identity", "audit", "directory", "catalog"}

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = MigrationSettings()
config.attributes.setdefault("app_db_role", settings.app_db_role)


def include_name(name: str | None, type_: str, _parent: object) -> bool:
    if type_ == "schema":
        return name in MANAGED_SCHEMAS
    return True


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        include_schemas=True,
        include_name=include_name,
        transaction_per_migration=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(
        settings.migration_database_url, connect_args={"prepare_threshold": None}
    )
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    raise SystemExit("Offline migrations are not supported; run against a database.")

loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
asyncio.run(run_async_migrations(), loop_factory=loop_factory)
