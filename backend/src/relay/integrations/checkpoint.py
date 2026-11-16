"""Incremental connector sync: resume from the last success, reconcile the full window daily."""

from datetime import datetime, timedelta
from typing import Protocol

SYNC_OVERLAP = timedelta(minutes=15)
RECONCILE_EVERY = timedelta(days=1)


class Checkpointed(Protocol):
    sync_cursor: datetime | None
    reconciled_at: datetime | None


def activity_window(connection: Checkpointed, now: datetime, days: int) -> tuple[datetime, bool]:
    """Where this sync reads activity from, and whether it is a full (reconciling) run.

    Incremental runs start at the last successful run minus an overlap, so nothing updated
    while that run was in flight is missed; writes are upserts, so the overlap is harmless.
    A full window runs first and then daily, to catch anything an incremental run missed.
    """
    window = now - timedelta(days=days)
    cursor, reconciled = connection.sync_cursor, connection.reconciled_at
    if cursor is None or reconciled is None or now - reconciled >= RECONCILE_EVERY:
        return window, True
    return max(cursor - SYNC_OVERLAP, window), False


def advance(connection: Checkpointed, started: datetime, *, full: bool) -> None:
    """Record a fully successful run (call only then): the next run resumes from `started`."""
    connection.sync_cursor = started
    if full:
        connection.reconciled_at = started
