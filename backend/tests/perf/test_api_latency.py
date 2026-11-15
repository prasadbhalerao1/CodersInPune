"""API latency at a realistic dataset size (NFR-PERF-001/002/004). Opt-in: `RELAY_PERF=1`.

Runs in-process against real PostgreSQL as `relay_app`, with RLS and authorization on. It
measures the API and database only: no network hop, TLS, browser or WorkOS round trip.
Prints p50/p95 per endpoint; asserts the SRS targets so regressions fail loudly.
"""

import os
import statistics
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import pytest

from tests.api import OWNER, Api, Ws, make_api

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(os.environ.get("RELAY_PERF") != "1", reason="set RELAY_PERF=1"),
]

PEOPLE, RESPONSIBILITIES, CASES, ROUNDS = 250, 1000, 60, 30


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with make_api() as a:
        yield a


async def _measure(call: Callable[[], Awaitable[Any]]) -> tuple[float, float]:
    await call()  # warm-up
    times = []
    for _ in range(ROUNDS):
        started = time.perf_counter()
        await call()
        times.append((time.perf_counter() - started) * 1000)
    times.sort()
    return statistics.median(times), times[int(len(times) * 0.95) - 1]


async def test_latency_at_pilot_scale(api: Api) -> None:
    ws = Ws(api, await api.create_workspace(OWNER, "Perf"))
    people = [await ws.person(f"Person {i:04d}") for i in range(PEOPLE)]
    duties = []
    for i in range(RESPONSIBILITIES):
        rid = await ws.responsibility(f"Responsibility {i:04d}", ("standard", "high")[i % 2])
        if i % 2:
            await ws.call(
                "POST",
                f"/responsibilities/{rid}/assignments",
                201,
                json={"role": "primary", "person_id": people[i % PEOPLE]},
            )
        duties.append(rid)
    for i in range(CASES):
        await ws.call(
            "POST",
            "/cases",
            201,
            json={
                "case_type": "transfer",
                "title": f"Transfer {i:03d}",
                "starts_at": "2026-12-01T09:00:00Z",
            },
        )

    reads = {
        "GET /responsibilities (page of 500)": lambda: ws.call("GET", "/responsibilities"),
        "GET /responsibilities/{id}": lambda: ws.call("GET", f"/responsibilities/{duties[7]}"),
        "GET /people (page of 250)": lambda: ws.call("GET", "/people"),
        "GET /cases": lambda: ws.call("GET", "/cases"),
        "GET /overview": lambda: ws.call("GET", "/overview"),
        "GET /risks": lambda: ws.call("GET", "/risks"),
        "GET /search?q=Responsibility 04": lambda: ws.call(
            "GET", "/search", params={"q": "Responsibility 04"}
        ),
    }
    counter = iter(range(10_000))
    writes = {
        "POST /people": lambda: ws.call(
            "POST", "/people", 201, json={"display_name": f"New {next(counter)}"}
        ),
        "POST /responsibilities/{id}/knowledge": lambda: ws.call(
            "POST",
            f"/responsibilities/{duties[3]}/knowledge",
            201,
            json={"kind": "note", "title": f"Note {next(counter)}", "body": "x"},
        ),
    }
    results = {name: await _measure(call) for name, call in {**reads, **writes}.items()}
    print(f"\nDataset: {PEOPLE} people, {RESPONSIBILITIES} responsibilities, {CASES} cases")
    for name, (p50, p95) in results.items():
        print(f"{name:40s} p50 {p50:7.1f} ms   p95 {p95:7.1f} ms")
    for name in reads:
        limit = 2000 if "search" in name else 500
        assert results[name][1] < limit, name
    for name in writes:
        assert results[name][1] < 800, name
