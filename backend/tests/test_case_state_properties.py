"""Property tests for the case state machine: seeded random walks over `lifecycle.allowed`.

The walks use the real transition rules and apply `move`'s bookkeeping (`blocked_from`),
then check invariants that must hold for every reachable path, not just the happy one.
"""

import random
from itertools import pairwise
from dataclasses import dataclass

from relay.continuity import lifecycle

STATES = (*lifecycle.TRANSITIONS, "blocked")
OPEN = tuple(s for s in STATES if s not in lifecycle.CLOSED)


@dataclass
class _Case:
    status: str = "draft"
    blocked_from: str | None = None


def _step(case: _Case, to: str) -> None:
    case.blocked_from = case.status if to == "blocked" else None
    case.status = to


def _walks(n: int = 3000, length: int = 40) -> list[list[str]]:
    rng = random.Random(20261110)  # noqa: S311  (reproducible test walks, not security)
    paths = []
    for _ in range(n):
        case, path = _Case(), ["draft"]
        for _ in range(length):
            options = [s for s in STATES if s != case.status and lifecycle.allowed(case, s)]  # type: ignore[arg-type]
            if not options:
                break
            _step(case, rng.choice(options))
            path.append(case.status)
        paths.append(path)
    return paths


PATHS = _walks()


def test_every_state_is_reachable_from_draft() -> None:
    assert {s for p in PATHS for s in p} == set(STATES)


def test_completion_only_follows_execution() -> None:
    for path in PATHS:
        for before, after in pairwise(path):
            if after == "completed":
                assert before in lifecycle.RUNNING, path


def test_closed_cases_only_reopen() -> None:
    for path in PATHS:
        for before, after in pairwise(path):
            if before in lifecycle.CLOSED:
                assert after == "reopened", path


def test_blocked_returns_to_where_it_was_or_cancels() -> None:
    for path in PATHS:
        for i in range(1, len(path) - 1):
            if path[i] == "blocked":
                assert path[i + 1] in (path[i - 1], "cancelled"), path


def test_running_cases_are_never_cancelled_directly() -> None:
    for path in PATHS:
        for before, after in pairwise(path):
            if after == "cancelled":
                assert before not in lifecycle.RUNNING, path
