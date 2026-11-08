from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from relay.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    """Create the application engine (restricted app role).

    `prepare_threshold=None` disables server-side prepared statements so the same
    configuration works behind a transaction-mode connection pooler (Register D23).
    """
    return create_async_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
        connect_args={"prepare_threshold": None},
    )
