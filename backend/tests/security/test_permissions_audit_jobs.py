"""Permissions, append-only audit log, transactional outbox and the Procrastinate worker.

Real PostgreSQL as `relay_app` throughout; the worker runs the real Procrastinate worker.
"""

import uuid
from collections.abc import AsyncIterator
from typing import Any, cast

import anyio
import psycopg
import pytest
from sqlalchemy import ColumnElement, delete, select, text, update
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from relay.audit.models import AuditEvent
from relay.identity.workspace_access import WorkspaceAccess
from relay.jobs import outbox
from relay.jobs.app import create_job_app
from relay.jobs.models import OutboxEvent
from relay.policy.permissions import (
    Permission,
    PermissionDenied,
    authorize,
    role_allows,
    visible,
)
from relay.shared.db import unit_of_work
from tests.api import Api, add_member, make_api
from tests.conftest import make_settings
from tests.db import OWNER_URL, count_rows, libpq_url

pytestmark = pytest.mark.anyio


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with make_api() as a:
        yield a


async def outbox_event_id(api: Api, tenant: uuid.UUID) -> uuid.UUID:
    async with unit_of_work(api.app.state.session_factory, tenant) as session:
        return (await session.scalars(select(OutboxEvent.id))).one()


def fake_access(role: str, tenant: uuid.UUID | None = None) -> WorkspaceAccess:
    return WorkspaceAccess(
        session=cast(AsyncSession, None),
        tenant_id=tenant or uuid.uuid4(),
        user_id=uuid.uuid4(),
        membership_id=uuid.uuid4(),
        role=role,
        workos_user_id="user_x",
    )


# Permission registry


def test_owner_has_existing_permissions_and_unknowns_are_denied() -> None:
    assert role_allows("owner", Permission.WORKSPACE_READ)
    assert role_allows("owner", Permission.AUDIT_READ)
    assert not role_allows("member", Permission.AUDIT_READ)
    assert not role_allows("owner", "workspace.delete")  # unknown permission
    assert not role_allows("superuser", Permission.WORKSPACE_READ)  # unknown role
    with pytest.raises(PermissionDenied):
        authorize(fake_access("owner"), "made.up")


def test_visible_scopes_to_the_authorized_workspace_or_nothing() -> None:
    tenant = uuid.uuid4()

    def sql(clause: ColumnElement[bool]) -> str:
        dialect = postgresql.dialect()  # type: ignore[no-untyped-call]
        return str(clause.compile(dialect=dialect, compile_kwargs={"literal_binds": True}))

    allowed = sql(
        visible(fake_access("owner", tenant), Permission.AUDIT_READ, AuditEvent.tenant_id)
    )
    assert str(tenant) in allowed
    denied = visible(fake_access("member", tenant), Permission.AUDIT_READ, AuditEvent.tenant_id)
    assert sql(denied) == "false"


async def test_owner_can_read_audit_events(api: Api) -> None:
    workspace = await api.create_workspace("user_owner", "Acme")
    response = await api.client.get(
        f"/workspaces/{workspace}/audit-events", headers=api.as_user("user_owner")
    )
    assert response.status_code == 200
    actions = {e["action"] for e in response.json()}
    assert {"workspace.created", "membership.created"} <= actions


async def test_member_without_permission_is_denied_and_denial_is_audited(api: Api) -> None:
    workspace = await api.create_workspace("user_owner", "Acme")
    await add_member(api, workspace, "user_member", "member")
    response = await api.client.get(
        f"/workspaces/{workspace}/audit-events", headers=api.as_user("user_member")
    )
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"
    assert (
        count_rows(
            "audit.audit_event",
            "tenant_id = %s AND action = 'authorization.denied' "
            "AND metadata->>'permission' = 'audit.read'",
            (workspace,),
        )
        == 1
    )
    # The member can still read the workspace itself.
    ok = await api.client.get(f"/workspaces/{workspace}", headers=api.as_user("user_member"))
    assert ok.status_code == 200


async def test_audit_events_of_another_workspace_are_unreachable(api: Api) -> None:
    mine = await api.create_workspace("user_a", "Mine")
    theirs = await api.create_workspace("user_b", "Theirs")
    response = await api.client.get(
        f"/workspaces/{theirs}/audit-events", headers=api.as_user("user_a")
    )
    assert response.status_code == 404
    own = await api.client.get(f"/workspaces/{mine}/audit-events", headers=api.as_user("user_a"))
    assert all(e["target_id"] != str(theirs) for e in own.json())


async def test_service_cannot_be_called_around_authorization(api: Api) -> None:
    workspace = await api.create_workspace("user_owner", "Acme")
    from relay.audit import service as audit_service

    with pytest.raises(PermissionDenied):
        await audit_service.list_events(fake_access("guest", workspace))


# Audit log


async def test_workspace_creation_writes_audit_outbox_and_job_together(api: Api) -> None:
    workspace = await api.create_workspace("user_owner", "Acme")
    tenant = "tenant_id = %s"
    assert (
        count_rows("audit.audit_event", f"{tenant} AND action = 'workspace.created'", (workspace,))
        == 1
    )
    assert (
        count_rows("audit.audit_event", f"{tenant} AND action = 'membership.created'", (workspace,))
        == 1
    )
    assert (
        count_rows("platform.outbox_event", f"{tenant} AND processed_at IS NULL", (workspace,)) == 1
    )
    # The job carries identifiers only; tenant data stays in the RLS-protected outbox.
    event_id = await outbox_event_id(api, workspace)
    assert (
        count_rows(
            "public.procrastinate_jobs",
            "task_name = %s AND args = %s::jsonb AND status = 'todo'",
            (outbox.PROCESS_TASK, f'{{"tenant_id": "{workspace}", "event_id": "{event_id}"}}'),
        )
        == 1
    )


async def test_audit_records_cannot_be_modified_or_deleted(api: Api) -> None:
    workspace = await api.create_workspace("user_owner", "Acme")
    for statement in (
        update(AuditEvent).values(action="tampered.event"),
        delete(AuditEvent),
    ):
        with pytest.raises(DBAPIError) as excinfo:
            async with unit_of_work(api.app.state.session_factory, workspace) as session:
                await session.execute(statement)
        assert isinstance(excinfo.value.orig, psycopg.errors.InsufficientPrivilege)
    # Even the owning role is stopped by the append-only trigger.
    with psycopg.connect(libpq_url(OWNER_URL)) as conn:
        conn.execute("SELECT set_config('app.tenant_id', %s, true)", (str(workspace),))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("UPDATE audit.audit_event SET action = 'tampered.event'")


async def test_failure_after_outbox_write_leaves_no_partial_records(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_emit = outbox.emit

    async def emit_then_fail(*args: Any, **kwargs: Any) -> uuid.UUID:
        await real_emit(*args, **kwargs)  # outbox row + Procrastinate job + audit pending
        raise RuntimeError("crash after enqueue")

    monkeypatch.setattr(outbox, "emit", emit_then_fail)
    # The test transport re-raises unhandled app errors (a real server would return 500).
    with pytest.raises(RuntimeError, match="crash after enqueue"):
        await api.client.post(
            "/workspaces",
            json={"name": "Doomed"},
            headers={**api.as_user("user_doomed"), "Idempotency-Key": "doomed-key-1"},
        )
    for table in (
        "platform.tenant",
        "identity.membership",
        "audit.audit_event",
        "platform.outbox_event",
        "public.procrastinate_jobs",
    ):
        assert count_rows(table) == 0, table


# Outbox processing


async def test_duplicate_delivery_processes_once(api: Api) -> None:
    workspace = await api.create_workspace("user_owner", "Acme")
    event_id = await outbox_event_id(api, workspace)
    factory = api.app.state.session_factory
    results: list[bool] = []

    async def deliver() -> None:
        results.append(await outbox.process(factory, workspace, event_id))

    async with anyio.create_task_group() as tg:
        for _ in range(3):
            tg.start_soon(deliver)
    results.append(await outbox.process(factory, workspace, event_id))

    assert sorted(results) == [False, False, False, True]
    processed = "action = 'job.outbox_event.processed' AND target_id = %s"
    assert count_rows("audit.audit_event", processed, (event_id,)) == 1
    assert (
        count_rows("platform.outbox_event", "id = %s AND processed_at IS NOT NULL", (event_id,))
        == 1
    )


async def test_worker_cannot_process_another_tenants_event(api: Api) -> None:
    a_ws = await api.create_workspace("user_a", "A")
    b_ws = await api.create_workspace("user_b", "B")
    a_event = await outbox_event_id(api, a_ws)

    processed = await outbox.process(api.app.state.session_factory, b_ws, a_event)

    assert processed is False
    assert count_rows("platform.outbox_event", "id = %s AND processed_at IS NULL", (a_event,)) == 1
    assert count_rows("audit.audit_event", "action LIKE 'job.%%'") == 0


async def test_failed_processing_is_recorded_and_retryable(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = await api.create_workspace("user_owner", "Acme")
    event_id = await outbox_event_id(api, workspace)
    factory = api.app.state.session_factory

    async def broken(_session: AsyncSession, _event: OutboxEvent) -> None:
        raise ConnectionError("downstream unavailable")

    monkeypatch.setitem(outbox.HANDLERS, "workspace.created", broken)
    with pytest.raises(ConnectionError):
        await outbox.process(factory, workspace, event_id)
    assert (
        count_rows(
            "platform.outbox_event",
            "id = %s AND processed_at IS NULL AND attempts = 1 "
            "AND last_error_type = 'ConnectionError'",
            (event_id,),
        )
        == 1
    )
    assert count_rows("audit.audit_event", "action = 'job.outbox_event.failed'") == 1

    monkeypatch.undo()
    assert await outbox.process(factory, workspace, event_id) is True
    assert count_rows("platform.outbox_event", "id = %s AND attempts = 2", (event_id,)) == 1


async def test_real_worker_processes_deferred_job_as_app_role(api: Api) -> None:
    workspace = await api.create_workspace("user_owner", "Acme")
    event_id = await outbox_event_id(api, workspace)

    jobs = create_job_app(make_settings(), api.app.state.session_factory)
    async with jobs.open_async():
        await jobs.run_worker_async(wait=False, install_signal_handlers=False)

    assert count_rows("public.procrastinate_jobs", "status = 'succeeded'") == 1
    assert (
        count_rows("platform.outbox_event", "id = %s AND processed_at IS NOT NULL", (event_id,))
        == 1
    )
    # Worker connections are the restricted role.
    with psycopg.connect(libpq_url(OWNER_URL)) as conn:
        row = conn.execute(
            "SELECT rolbypassrls, rolsuper FROM pg_roles r "
            "JOIN pg_class c ON c.relname = 'procrastinate_jobs' "
            "WHERE r.rolname = 'relay_app'"
        ).fetchone()
    assert row == (False, False)


async def test_job_without_tenant_context_sees_no_events(api: Api) -> None:
    workspace = await api.create_workspace("user_owner", "Acme")
    async with unit_of_work(api.app.state.session_factory, None) as session:
        assert await session.scalar(text("SELECT count(*) FROM platform.outbox_event")) == 0
    assert count_rows("platform.outbox_event", "tenant_id = %s", (workspace,)) == 1
