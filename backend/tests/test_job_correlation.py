"""Job logs carry the outbox event id as their correlation id (NFR-OBS-A02)."""

import logging
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from relay.jobs import outbox
from relay.shared.observability import REQUEST_ID

pytestmark = pytest.mark.anyio


async def test_job_logs_use_the_event_id_and_restore_the_previous_context(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    seen: list[str | None] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            seen.append(REQUEST_ID.get())

    handler = Capture()
    logging.getLogger("relay.jobs.outbox").addHandler(handler)
    event_id = uuid.uuid7()
    try:
        # An event that isn't visible is logged and skipped: enough to see the context.
        assert not await outbox.process(session_factory, uuid.uuid7(), event_id)
    finally:
        logging.getLogger("relay.jobs.outbox").removeHandler(handler)
    assert seen == [event_id.hex]
    assert REQUEST_ID.get() is None
