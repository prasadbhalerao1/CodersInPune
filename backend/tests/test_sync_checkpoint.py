"""Incremental GitHub sync: overlap from the last success, a full window daily."""

from datetime import UTC, datetime, timedelta

from relay.integrations.checkpoint import SYNC_OVERLAP, activity_window, advance
from relay.integrations.github.models import GitHubInstallation
from relay.integrations.linear.models import LinearConnection

NOW = datetime(2026, 11, 16, 12, tzinfo=UTC)


def _inst(cursor: datetime | None, reconciled: datetime | None) -> GitHubInstallation:
    return GitHubInstallation(sync_cursor=cursor, reconciled_at=reconciled)


def test_first_sync_reads_the_full_window() -> None:
    since, full = activity_window(_inst(None, None), NOW, 90)
    assert (since, full) == (NOW - timedelta(days=90), True)


def test_next_sync_resumes_from_the_checkpoint_with_overlap() -> None:
    last = NOW - timedelta(hours=2)
    since, full = activity_window(_inst(last, NOW - timedelta(hours=3)), NOW, 90)
    assert (since, full) == (last - SYNC_OVERLAP, False)


def test_a_full_reconciling_window_runs_daily() -> None:
    since, full = activity_window(_inst(NOW - timedelta(hours=1), NOW - timedelta(days=2)), NOW, 90)
    assert (since, full) == (NOW - timedelta(days=90), True)


def test_an_old_checkpoint_never_reads_beyond_the_window() -> None:
    old = NOW - timedelta(days=400)
    since, _ = activity_window(_inst(old, NOW - timedelta(hours=1)), NOW, 90)
    assert since == NOW - timedelta(days=90)


def test_linear_uses_the_same_checkpoint() -> None:
    connection = LinearConnection(sync_cursor=None, reconciled_at=None)
    _, full = activity_window(connection, NOW, 90)
    assert full
    advance(connection, NOW, full=full)
    assert (connection.sync_cursor, connection.reconciled_at) == (NOW, NOW)
    later = NOW + timedelta(hours=1)
    assert activity_window(connection, later, 90) == (NOW - SYNC_OVERLAP, False)
    advance(connection, later, full=False)
    assert (connection.sync_cursor, connection.reconciled_at) == (later, NOW)
