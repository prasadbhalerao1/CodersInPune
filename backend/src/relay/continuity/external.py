"""Approved external task actions: mirror a Relay task as a GitHub or Linear issue.

1. A case manager reviews the destination and the exact title and body, and approves.
2. Relay records the approval (the content is stored and sent unchanged) and queues it.
3. The worker performs one create-only call. The created issue carries the idempotency
   key, so a request that timed out (the provider may have accepted it) is recovered by
   finding the issue instead of creating a second one.
4. Relay records the external id, URL and a receipt on the action and the task.
5. "Check status" reconciles completion: a closed/completed issue completes the task.

No AI capability can call any of this: it is reachable only through a manager's approval.
Writes stay off until the provider permission is configured (config: github_issue_writes,
linear_issue_writes + an OAuth scope that includes issue creation).
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import procrastinate
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from relay.audit import service as audit
from relay.config import Settings
from relay.continuity import service as cases
from relay.continuity.models import CaseTask, CaseTaskEvent, ExternalAction
from relay.identity.workspace_access import WorkspaceAccess
from relay.integrations.github.client import GitHubClient, GitHubError
from relay.integrations.github.models import GitHubInstallation, GitHubRepository
from relay.integrations.linear import service as linear_service
from relay.integrations.linear.client import LinearClient, LinearError
from relay.integrations.linear.models import LinearConnection, LinearTeam
from relay.jobs import outbox
from relay.jobs.models import OutboxEvent
from relay.policy.permissions import Permission, authorize, visible
from relay.shared.api_types import LongText, Name, StrictInput
from relay.shared.errors import ApiError

EVENT = "external.execute"
MAX_ATTEMPTS = 5
RECHECK_AFTER = timedelta(minutes=1)
Provider = Literal["github", "linear"]


class ExternalActionIn(StrictInput):
    provider: Provider
    target: str  # GitHub "owner/repo" or a Linear team id
    title: Name
    body: LongText = ""


class TargetView(BaseModel):
    provider: Provider
    target: str
    label: str


class TargetsView(BaseModel):
    github_enabled: bool
    linear_enabled: bool
    # Why a provider can't be used yet, in words an admin can act on.
    github_blocker: str | None
    linear_blocker: str | None
    targets: list[TargetView]


class ExternalActionView(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    provider: str
    target_label: str
    title: str
    body: str
    state: str
    attempts: int
    external_id: str | None
    external_url: str | None
    error: str | None
    receipt: dict[str, Any]
    approved_by_name: str | None
    approved_at: datetime


def _blockers(settings: Settings) -> tuple[str | None, str | None]:
    github = (
        None
        if settings.github_issue_writes
        else "Turn on GitHub issue creation after granting the GitHub App "
        "“Issues: Read and write” (RELAY_GITHUB_ISSUE_WRITES)."
    )
    linear_scope = settings.linear_oauth_scope
    linear = (
        None
        if settings.linear_issue_writes
        and ("write" in linear_scope or "issues:create" in linear_scope)
        else "Turn on Linear issue creation and reconnect Linear with an issue-creation scope "
        "(RELAY_LINEAR_ISSUE_WRITES, RELAY_LINEAR_OAUTH_SCOPE)."
    )
    return github, linear


def _view(a: ExternalAction, names: dict[uuid.UUID, str]) -> ExternalActionView:
    return ExternalActionView(
        id=a.id,
        task_id=a.task_id,
        provider=a.provider,
        target_label=a.target_label,
        title=a.title,
        body=a.body,
        state=a.state,
        attempts=a.attempts,
        external_id=a.external_id,
        external_url=a.external_url,
        error=a.error,
        receipt=a.receipt,
        approved_by_name=names.get(a.approved_by),
        approved_at=a.approved_at,
    )


async def targets(access: WorkspaceAccess, settings: Settings) -> TargetsView:
    authorize(access, Permission.CASE_MANAGE)
    github_blocker, linear_blocker = _blockers(settings)
    found: list[TargetView] = []
    for repo in await access.session.scalars(
        select(GitHubRepository)
        .where(
            visible(access, Permission.CASE_MANAGE, GitHubRepository.tenant_id),
            GitHubRepository.accessible.is_(True),
            GitHubRepository.archived.is_(False),
            GitHubRepository.selected.is_(True),
        )
        .order_by(GitHubRepository.full_name)
    ):
        found.append(TargetView(provider="github", target=repo.full_name, label=repo.full_name))
    for team in await access.session.scalars(
        select(LinearTeam)
        .where(
            visible(access, Permission.CASE_MANAGE, LinearTeam.tenant_id),
            LinearTeam.removed.is_(False),
        )
        .order_by(LinearTeam.name)
    ):
        found.append(
            TargetView(provider="linear", target=team.linear_id, label=f"{team.key} · {team.name}")
        )
    return TargetsView(
        github_enabled=github_blocker is None,
        linear_enabled=linear_blocker is None,
        github_blocker=github_blocker,
        linear_blocker=linear_blocker,
        targets=found,
    )


async def task_actions(
    access: WorkspaceAccess, case_id: uuid.UUID, task_id: uuid.UUID
) -> list[ExternalActionView]:
    authorize(access, Permission.CASE_READ)
    await cases._load(access, case_id)
    names = await cases._member_names(access)
    rows = await access.session.scalars(
        select(ExternalAction)
        .where(ExternalAction.task_id == task_id)
        .order_by(ExternalAction.approved_at.desc())
    )
    return [_view(a, names) for a in rows]


async def approve(
    access: WorkspaceAccess,
    case_id: uuid.UUID,
    task_id: uuid.UUID,
    data: ExternalActionIn,
    settings: Settings,
    jobs: procrastinate.App,
) -> ExternalActionView:
    """Record the human approval of this exact destination and content, then queue it."""
    case = await cases._for_change(access, case_id, cases.OPEN)
    task = await access.session.get(CaseTask, task_id, with_for_update=True)
    if task is None or task.case_id != case_id:
        raise ApiError(404, "task_not_found", "Task not found.")
    choices = await targets(access, settings)
    blocker = choices.github_blocker if data.provider == "github" else choices.linear_blocker
    if blocker:
        raise ApiError(409, "writes_disabled", blocker)
    target = next(
        (t for t in choices.targets if t.provider == data.provider and t.target == data.target),
        None,
    )
    if target is None:
        raise ApiError(422, "target_not_found", "Choose a repository or team Relay can reach.")
    live = await access.session.scalar(
        select(ExternalAction.id).where(
            ExternalAction.task_id == task_id, ExternalAction.state != "failed"
        )
    )
    if live is not None:
        raise ApiError(409, "already_mirrored", "This task already has an external issue.")
    action_id = uuid.uuid7()
    action = ExternalAction(
        id=action_id,
        tenant_id=access.tenant_id,
        task_id=task_id,
        provider=data.provider,
        target=target.target,
        target_label=target.label,
        title=data.title,
        body=data.body,
        idempotency_key=f"relay-{action_id}",
        approved_by=access.user_id,
    )
    access.session.add(action)
    task.external_provider, task.sync_status = data.provider, "pending"
    await access.session.flush()
    cases._record(
        access, case, "case.external_action_approved", provider=data.provider, task_id=str(task_id)
    )
    await outbox.emit(
        access.session,
        jobs,
        tenant_id=access.tenant_id,
        event_type=EVENT,
        payload={"action_id": str(action_id)},
    )
    return _view(action, await cases._member_names(access))


async def retry(
    access: WorkspaceAccess, action_id: uuid.UUID, jobs: procrastinate.App
) -> ExternalActionView:
    """Retry with the same idempotency key: a request that did land is found, not repeated."""
    authorize(access, Permission.CASE_MANAGE)
    action = await access.session.get(ExternalAction, action_id, with_for_update=True)
    if action is None:
        raise ApiError(404, "action_not_found", "External action not found.")
    if action.state not in ("failed", "uncertain"):
        raise ApiError(409, "invalid_state", f"Nothing to retry: the action is {action.state}.")
    action.state, action.error, action.attempts = "approved", None, 0
    action.updated_at = func.now()
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="external_action.retried",
        actor_user_id=access.user_id,
        target_type="external_action",
        target_id=action.id,
        details={"provider": action.provider},
    )
    await outbox.emit(
        access.session,
        jobs,
        tenant_id=access.tenant_id,
        event_type=EVENT,
        payload={"action_id": str(action.id)},
    )
    await access.session.flush()
    return _view(action, await cases._member_names(access))


def _footer(action: ExternalAction) -> str:
    # Visible on purpose: it is how Relay recognises its own issue after a timeout.
    return f"\n\n---\nCreated from Relay after approval · ref {action.idempotency_key}"


async def _github_token(session: AsyncSession, client: GitHubClient, full_name: str) -> str:
    installation_id = await session.scalar(
        select(GitHubInstallation.installation_id)
        .join(GitHubRepository, GitHubRepository.installation_ref == GitHubInstallation.id)
        .where(GitHubRepository.full_name == full_name, GitHubInstallation.status == "active")
    )
    if installation_id is None:
        raise GitHubError(404, "The GitHub installation for this repository is no longer active.")
    return await client.installation_token(installation_id)


async def _linear_token(session: AsyncSession, client: LinearClient, settings: Settings) -> str:
    connection = await session.scalar(
        select(LinearConnection).where(LinearConnection.status == "active").with_for_update()
    )
    token = await linear_service.usable_token(connection, client, settings) if connection else None
    if token is None:
        raise LinearError(401, "Linear is not connected; reconnect it to create issues.")
    return token


async def _create_or_find(
    session: AsyncSession, action: ExternalAction, ctx: outbox.JobContext
) -> dict[str, str]:
    """Find the issue first when an earlier attempt may have landed; otherwise create it."""
    assert ctx.http is not None
    assert ctx.settings is not None
    marker = action.idempotency_key
    if action.provider == "github":
        github = GitHubClient(ctx.settings, ctx.http)
        token = await _github_token(session, github, action.target)
        found = (
            await github.find_issue(token, action.target, marker) if action.attempts > 1 else None
        )
        issue = found or await github.create_issue(
            token, action.target, action.title, action.body + _footer(action)
        )
        return {
            "id": str(issue["number"]),
            "url": str(issue["html_url"]),
            "found": str(bool(found)),
        }
    linear = LinearClient(ctx.settings, ctx.http)
    token = await _linear_token(session, linear, ctx.settings)
    found = await linear.find_issue(token, marker) if action.attempts > 1 else None
    issue = found or await linear.create_issue(
        token, action.target, action.title, action.body + _footer(action)
    )
    return {"id": str(issue["id"]), "url": str(issue["url"]), "found": str(bool(found))}


async def handle_execute(session: AsyncSession, event: OutboxEvent, ctx: outbox.JobContext) -> None:
    """Idempotent executor: a succeeded action is never sent again."""
    action = await session.get(
        ExternalAction, uuid.UUID(event.payload["action_id"]), with_for_update=True
    )
    if action is None or action.state in ("succeeded", "failed"):
        return
    action.state, action.attempts = "executing", action.attempts + 1
    action.updated_at = func.now()
    await session.flush()
    try:
        result = await _create_or_find(session, action, ctx)
    except (GitHubError, LinearError) as exc:
        transient = exc.transient
        if transient and action.attempts < MAX_ATTEMPTS:
            # The provider may have accepted it: look for it on the next attempt.
            action.state, action.error = "uncertain", f"{exc} — checking again shortly"
            assert ctx.jobs is not None
            await outbox.emit(
                session,
                ctx.jobs,
                tenant_id=action.tenant_id,
                event_type=EVENT,
                payload={"action_id": str(action.id), "attempt": action.attempts},
                schedule_at=datetime.now(UTC) + RECHECK_AFTER,
            )
        else:
            action.state, action.error = "failed", str(exc)
            task = await session.get(CaseTask, action.task_id)
            if task is not None:
                task.sync_status = "error"
        return
    action.state, action.error = "succeeded", None
    action.external_id, action.external_url = result["id"], result["url"]
    action.receipt = {
        "provider": action.provider,
        "target": action.target_label,
        "external_id": result["id"],
        "url": result["url"],
        "recovered_existing": result["found"] == "True",
        "attempts": action.attempts,
        "at": datetime.now(UTC).isoformat(),
    }
    task = await session.get(CaseTask, action.task_id)
    if task is not None:
        task.external_provider = action.provider
        task.external_id, task.external_url, task.sync_status = (
            result["id"],
            result["url"],
            "synced",
        )
    audit.record(
        session,
        tenant_id=action.tenant_id,
        action="external_action.succeeded",
        actor_user_id=None,
        target_type="external_action",
        target_id=action.id,
        details={"provider": action.provider, "attempts": action.attempts},
    )


async def check_status(
    access: WorkspaceAccess, action_id: uuid.UUID, ctx: outbox.JobContext
) -> ExternalActionView:
    """Reconcile completion from the provider: a closed/completed issue completes the task."""
    authorize(access, Permission.CASE_MANAGE)
    action = await access.session.get(ExternalAction, action_id)
    if action is None or action.state != "succeeded" or action.external_id is None:
        raise ApiError(409, "not_created", "The external issue hasn't been created.")
    assert ctx.http is not None
    assert ctx.settings is not None
    try:
        if action.provider == "github":
            github = GitHubClient(ctx.settings, ctx.http)
            token = await _github_token(access.session, github, action.target)
            state = await github.issue_state(token, action.target, int(action.external_id))
            done = state == "closed"
        else:
            linear = LinearClient(ctx.settings, ctx.http)
            token = await _linear_token(access.session, linear, ctx.settings)
            state = await linear.issue_state(token, action.external_id)
            done = state in ("completed", "canceled")
    except (GitHubError, LinearError) as exc:
        raise ApiError(
            502, "provider_unavailable", f"Couldn't reach {action.provider}: {exc}"
        ) from exc
    task = await access.session.get(CaseTask, action.task_id, with_for_update=True)
    if state is None and task is not None:
        task.sync_status = "unlinked"
    elif done and task is not None and task.status == "open":
        task.status, task.completed_at, task.completed_by = "done", func.now(), access.user_id
        access.session.add(
            CaseTaskEvent(
                tenant_id=access.tenant_id,
                task_id=task.id,
                kind="completed",
                body=f"Closed in {action.provider}",
                detail={"source": action.provider, "url": action.external_url},
                actor_user_id=access.user_id,
            )
        )
    await access.session.flush()
    return _view(action, await cases._member_names(access))


outbox.register(EVENT, handle_execute)
