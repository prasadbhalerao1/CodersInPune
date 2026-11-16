"""Seed a synthetic demo organisation: `uv run relay-demo-seed --owner <workos_user_id>`.

Also used by `POST /workspaces/sample` (relay.demo.api) so a new user can explore Relay
without connecting real sources. Creates a NEW workspace ("Northwind Labs (sample)") each
run, so it never touches real data, and drives the real services (rules, audit, outbox)
as synthetic members where a second person is needed. Everything is fictional; no
credentials are stored: the connector rows exist only to demonstrate health states and
are never synced.

What it sets up (SRS Appendix A/B):
- 2 departments, 3 teams, 8 people, 8 synthetic members (owner + 7 who can't sign in)
- a responsibility catalogue with primary / co-owner / backup coverage and gaps
- assets (one nobody stewards), conflicting procedures, a stale and an unverified page
- an ambiguous Linear identity, a stale Linear connector and a failing GitHub one
- a completed transfer, an active departure (blocker, tasks, analysis, interview,
  an approved handover capsule waiting for YOUR acknowledgement) and planned coverage
"""

# WHY DEMO ACCOUNTS EXIST: Relay is a real product. Anyone can sign in with their own email
# (WorkOS) and connect their real GitHub, Linear, Notion and Slack accounts; that is the normal
# path and uses exactly the same code. Doing that during judging would be slow, and a fresh
# organisation would not yet show the edge cases (a leaver, stale knowledge, conflicts, blocked
# handovers). So, to give judges the full experience in minutes, we also ship pre-seeded
# sample data and one shared demo account per role. Nothing here is a mock or a shortcut.

import argparse
import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import procrastinate
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert

from relay.catalog import assets as catalog_assets
from relay.catalog import knowledge, stewardship
from relay.catalog import service as catalog
from relay.catalog.models import KnowledgeItem, Responsibility, ResponsibilityDependency
from relay.config import Settings
from relay.continuity import service as cases
from relay.continuity import workflow
from relay.directory import service as directory
from relay.directory.models import Person
from relay.identity.models import Membership, UserAccount
from relay.identity.tokens import VerifiedIdentity
from relay.identity.workos_api import WorkOSClient, WorkOSUser
from relay.identity.workspace_access import WorkspaceAccess, open_workspace_access
from relay.integrations.github.models import GitHubInstallation, GitHubRepository, GitHubWorkItem
from relay.integrations.linear.models import (
    LinearConnection,
    LinearIdentity,
    LinearIssue,
    LinearProject,
)
from relay.integrations.notion.models import NotionConnection, NotionPage, NotionSource
from relay.intelligence import capsules, interviews, meetings, runs
from relay.jobs.app import create_job_app
from relay.platform import workspaces
from relay.platform.models import Tenant
from relay.platform.workspaces import WorkspaceView
from relay.policy.permissions import ROLE_PERMISSIONS
from relay.shared.db import create_engine, create_session_factory, unit_of_work

NOW = datetime.now(UTC)
SAMPLE_NAME = "Northwind Labs (sample)"
DOMAIN = "northwind.example"  # reserved for documentation: never a real mailbox
MEMBERS = {  # synthetic member id -> (role, display name)
    "demo_maya": ("admin", "Maya Chen"),
    "demo_tom": ("continuity_manager", "Tom Okafor"),
    "demo_priya": ("member", "Priya Nair"),
    "demo_arjun": ("member", "Arjun Rao"),
    "demo_sara": ("member", "Sara Kim"),
    "demo_ines": ("knowledge_steward", "Ines Duarte"),
    "demo_leo": ("member", "Leo Martins"),
    # One persona for each remaining role, so every role can be seen doing its job.
    "demo_dev": ("team_manager", "Dev Patel"),
    "demo_riya": ("auditor", "Riya Desai"),
    "demo_kai": ("guest", "Kai Nakamura"),
}


def _identity(sub: str) -> VerifiedIdentity:
    return VerifiedIdentity(
        workos_user_id=sub, session_id=None, expires_at=NOW + timedelta(hours=1)
    )


async def seed(owner: str) -> uuid.UUID:
    settings = Settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    jobs = create_job_app(settings, factory)
    try:
        async with jobs.open_async():
            workspace, _ = await seed_workspace(owner, settings, factory, jobs)
            return workspace.id
    finally:
        await engine.dispose()


async def seed_workspace(  # type: ignore[no-untyped-def]
    owner: str,
    settings: Settings,
    factory,
    jobs: procrastinate.App,
    idempotency_key: str | None = None,
    name: str = SAMPLE_NAME,
) -> tuple[WorkspaceView, bool]:
    """Create and populate a sample workspace owned by `owner`.

    Returns (workspace, created). Replaying the same idempotency key returns the original
    workspace without seeding it a second time.
    """
    ws, created = await workspaces.create_workspace(
        factory, jobs, _identity(owner), name, idempotency_key or f"demo-{uuid.uuid7()}"
    )
    if not created:
        return ws, False
    tenant = ws.id
    users: dict[str, uuid.UUID] = {}
    for sub, (role, name) in MEMBERS.items():
        async with unit_of_work(factory, tenant, sub) as session:
            user_id = (
                await session.execute(
                    insert(UserAccount)
                    .values(workos_user_id=sub)
                    .on_conflict_do_update(
                        index_elements=["workos_user_id"], set_={"workos_user_id": sub}
                    )
                    .returning(UserAccount.id)
                )
            ).scalar_one()
            first = name.split()[0].lower()
            session.add(
                Membership(
                    tenant_id=tenant,
                    user_id=user_id,
                    role=role,
                    status="active",
                    display_name=name,
                    email=f"{first}@{DOMAIN}",
                    member_type="contractor" if sub in ("demo_leo", "demo_kai") else "employee",
                )
            )
            users[sub] = user_id

    async with open_workspace_access(factory, _identity(owner), tenant) as access:
        # Marks the sample and its creator, who may try Relay as any role here.
        await access.session.execute(
            update(Tenant).where(Tenant.id == tenant).values(sample_owner_id=access.user_id)
        )
        ids = await _catalog(access, users)
        await _dependencies(access)
    async with open_workspace_access(factory, _identity(owner), tenant) as access:
        await _connectors(access, ids)
    async with open_workspace_access(factory, _identity(owner), tenant) as access:
        departure = await _cases(access, ids, users, settings, jobs)
    async with open_workspace_access(factory, _identity(owner), tenant) as access:
        await _meetings(access, ids, departure, settings, jobs)
    # A second manager approves the handover so the owner (the recipient) can acknowledge.
    async with open_workspace_access(factory, _identity("demo_maya"), tenant) as maya:
        capsule = await capsules.generate(
            maya,
            departure,
            capsules.CapsuleIn(recipient_user_id=(await _owner_id(maya))),
            settings,
            jobs,
        )
    async with open_workspace_access(factory, _identity("demo_maya"), tenant) as maya:
        await capsules.approve(maya, capsule.id)
    return ws, True


async def _owner_id(access: WorkspaceAccess) -> uuid.UUID:
    owner = await access.session.scalar(
        select(Membership.user_id).where(Membership.role == "owner")
    )
    assert owner is not None
    return owner


# Refunds need the payments API, which ships through the deploy pipeline: a chain the What If?
# simulator follows when the pipeline's owner is away. (dependent, depends on)
DEPENDENCIES = (
    ("Payments API operations", "Production deployments"),
    ("Refund approvals", "Payments API operations"),
)


async def _dependencies(access: WorkspaceAccess) -> None:
    """Record the sample's dependency chain; skips any already recorded, so reruns are safe."""
    by_name = {
        r.name: r.id
        for r in await access.session.scalars(
            select(Responsibility).where(Responsibility.tenant_id == access.tenant_id)
        )
    }
    for dependent, target in DEPENDENCIES:
        if dependent not in by_name or target not in by_name:
            continue
        exists = await access.session.scalar(
            select(func.count())
            .select_from(ResponsibilityDependency)
            .where(
                ResponsibilityDependency.responsibility_id == by_name[dependent],
                ResponsibilityDependency.depends_on_responsibility_id == by_name[target],
            )
        )
        if not exists:
            await stewardship.add_dependency(
                access,
                by_name[dependent],
                stewardship.DependencyIn(depends_on_responsibility_id=by_name[target]),
            )


async def _backfill_commits(access: WorkspaceAccess) -> None:
    """Give the sample's pull requests their commits if they were seeded before commits were
    read; pull requests that already have commits are left alone."""
    for item in await access.session.scalars(
        select(GitHubWorkItem).where(
            GitHubWorkItem.tenant_id == access.tenant_id,
            GitHubWorkItem.kind == "pull_request",
            GitHubWorkItem.number.in_(list(PR_COMMITS)),
            GitHubWorkItem.github_id >= 990000000,
        )
    ):
        if not item.commits:
            item.commits = _sample_commits(item.number, item.gh_updated_at)


def _sample_commits(number: int, at: datetime) -> list[dict[str, object]]:
    messages = PR_COMMITS.get(number, ())
    return [
        {
            "sha": f"{number:04d}{i:02d}a7c3e9",
            "message": message,
            "author": "leo-nw" if number in (31, 34) else "arjun-nw",
            "at": (at - timedelta(hours=6 * (len(messages) - i))).isoformat(),
        }
        for i, message in enumerate(messages)
    ]


async def _catalog(access: WorkspaceAccess, users: dict[str, uuid.UUID]) -> dict[str, uuid.UUID]:
    d = directory
    eng = await d.create_department(access, d.DepartmentIn(name="Engineering"))
    fin = await d.create_department(access, d.DepartmentIn(name="Finance Operations"))
    platform = await d.create_team(access, d.TeamIn(name="Platform", department_id=eng.id))
    payments = await d.create_team(access, d.TeamIn(name="Payments", department_id=eng.id))
    finops = await d.create_team(access, d.TeamIn(name="FinOps", department_id=fin.id))
    people: dict[str, uuid.UUID] = {}
    for key, name, title, dept, team in (
        ("maya", "Maya Chen", "Engineering manager", eng.id, platform.id),
        ("arjun", "Arjun Rao", "Senior platform engineer", eng.id, platform.id),
        ("leo", "Leo Martins", "Platform engineer (contractor)", eng.id, platform.id),
        ("priya", "Priya Nair", "Payments lead", eng.id, payments.id),
        ("sara", "Sara Kim", "Payments engineer", eng.id, payments.id),
        ("tom", "Tom Okafor", "FinOps lead", fin.id, finops.id),
        ("ines", "Ines Duarte", "Finance analyst", fin.id, finops.id),
        ("dev", "Dev Patel", "Platform engineer (joining)", eng.id, None),
    ):
        person = await d.create_person(
            access,
            d.PersonIn(
                display_name=name,
                email=f"{key}@{DOMAIN}",
                title=title,
                department_id=dept,
                github_login=f"{key}-nw" if key in ("arjun", "leo", "priya") else None,
            ),
        )
        people[key] = person.id
        if team:
            await d.add_team_member(access, team, person.id)
    for key in ("arjun", "leo", "dev"):
        await d.update_person(access, people[key], d.PersonUpdate(manager_person_id=people["maya"]))

    assets = {}
    for key, name, kind, crit in (
        ("payments_api", "payments-api", "service", "critical"),
        ("billing_db", "billing-db", "infrastructure", "critical"),
        ("stripe", "Stripe", "vendor", "high"),
        ("deploy_repo", "northwind/deploy-pipelines", "repository", "high"),
        ("legacy_ftp", "Legacy SFTP bridge", "infrastructure", "standard"),  # nobody stewards
    ):
        asset = await catalog_assets.create_asset(
            access, catalog_assets.AssetIn(name=name, asset_type=kind, criticality=crit)
        )
        assets[key] = asset.id

    r: dict[str, uuid.UUID] = {}
    for key, name, crit, desc in (
        ("deploys", "Production deployments", "critical", "Ship and roll back services safely."),
        ("oncall", "Platform on-call", "critical", "First response for platform incidents."),
        ("payments", "Payments API operations", "critical", "Keep checkout and refunds running."),
        ("refunds", "Refund approvals", "high", "Approve refunds above the auto-approval limit."),
        ("close", "Month-end close", "critical", "Reconcile and close the books monthly."),
        ("vendors", "Vendor contracts", "standard", "Renewals and vendor access reviews."),
        ("access", "Access reviews", "high", "Quarterly review of production access."),
    ):
        created = await catalog.add_responsibility(
            access,
            catalog.ResponsibilityIn(
                name=name,
                criticality=crit,
                description=desc,
                escalation_path="Page #platform-oncall, then Maya Chen"
                if key in ("deploys", "oncall")
                else None,
            ),
        )
        r[key] = created.id

    def assign(rid: str, role: str, person: str | None = None, team: uuid.UUID | None = None):  # type: ignore[no-untyped-def]
        return catalog.assign_owner(
            access,
            r[rid],
            catalog.AssignmentIn(
                role=role,
                person_id=people[person] if person else None,
                team_id=team,
                starts_at=NOW - timedelta(days=400),
            ),
        )

    await assign("deploys", "primary", "arjun")  # single-person dependency: Arjun leaves
    await assign("oncall", "primary", "arjun")
    await assign("oncall", "backup", "leo")
    await assign("payments", "primary", "priya")
    await assign("payments", "backup", "sara")
    await assign("refunds", "primary", "priya")  # no backup
    await assign("close", "primary", None, finops.id)  # team-owned critical, no contact
    await assign("close", "backup", "tom")  # backup inside the primary team
    await assign("vendors", "primary", "tom")
    await assign("vendors", "co_owner", "ines")
    await assign("access", "primary", "maya")
    for rid, asset_key in (
        ("deploys", "deploy_repo"),
        ("payments", "payments_api"),
        ("payments", "stripe"),
        ("close", "billing_db"),
    ):
        await catalog_assets.link_asset(
            access, r[rid], catalog_assets.AssetLinkIn(asset_id=assets[asset_key])
        )

    k = knowledge
    deploy_a = await k.add_knowledge(
        access,
        r["deploys"],
        k.KnowledgeIn(
            kind="procedure",
            title="Deploy payments-api",
            body="1. Merge to main. 2. Run the canary for 30 minutes. 3. Promote.",
        ),
    )
    await k.add_knowledge(  # conflicts with the one above
        access,
        r["deploys"],
        k.KnowledgeIn(
            kind="procedure",
            title="Deploy payments-api (old runbook)",
            body="1. Merge to main. 2. Promote directly; no canary needed.",
        ),
    )
    await k.add_knowledge(
        access,
        r["deploys"],
        k.KnowledgeIn(
            kind="adr",
            title="Every payments-api deploy goes through a canary",
            body="Promotion is blocked while the canary error rate is above baseline.",
            decision_rationale="A release went straight to production and took checkout "
            "down for 40 minutes.",
            decision_approver="Maya Chen",
            decided_at=NOW - timedelta(days=185),
        ),
    )
    await k.add_knowledge(
        access,
        r["oncall"],
        k.KnowledgeIn(
            kind="escalation_contact",
            title="Who to page for database incidents",
            body="DBA rota via #db-oncall; vendor support case for managed Postgres.",
        ),
    )
    stale = await k.add_knowledge(
        access,
        r["close"],
        k.KnowledgeIn(
            kind="procedure",
            title="Month-end close checklist",
            body="Export ledgers, reconcile Stripe payouts, lock the period.",
        ),
    )
    await k.add_knowledge(
        access,
        r["payments"],
        k.KnowledgeIn(
            kind="adr",
            title="Use idempotency keys for all refund calls",
            body="Every refund request carries an idempotency key derived from the order.",
            decision_rationale="Retries after timeouts created duplicate refunds in 2025.",
            decision_approver="Priya Nair",
        ),
    )
    # A stale page (reviewed 200 days ago) and an imported page nobody has verified yet.
    await access.session.execute(
        update(KnowledgeItem)
        .where(KnowledgeItem.id == stale.id)
        .values(last_reviewed_at=NOW - timedelta(days=200))
    )
    calendar_id = uuid.uuid7()
    access.session.add(
        KnowledgeItem(
            id=calendar_id,
            tenant_id=access.tenant_id,
            responsibility_id=r["deploys"],
            kind="document",
            title="Release calendar (imported)",
            body="Freeze windows: last week of each quarter.",
            origin="notion",
            review_state="draft",
            author_user_id=access.user_id,
            last_reviewed_at=None,
        )
    )
    return {
        **{f"p_{key}": v for key, v in people.items()},
        **{f"r_{key}": v for key, v in r.items()},
        "deploy_procedure": deploy_a.id,
        "release_calendar": calendar_id,
        "team_platform": platform.id,
    }


# The sample organisation's GitHub App installation (not a real installation id).
SAMPLE_GITHUB_INSTALLATION = 999000001


async def _connectors(access: WorkspaceAccess, ids: dict[str, uuid.UUID]) -> None:
    """Connector rows only for health states; no tokens, never synced."""
    linear = LinearConnection(
        tenant_id=access.tenant_id,
        organization_id="demo-org",
        organization_name="Northwind (demo Linear)",
        status="active",
        connected_by=access.user_id,
        last_synced_at=NOW - timedelta(days=3),  # stale
        last_sync_status="ok",
    )
    access.session.add(linear)
    await access.session.flush()
    access.session.add(
        LinearIdentity(  # ambiguous: two people could be "A. Rao"
            tenant_id=access.tenant_id,
            linear_id="demo-lu-arao",
            name="A. Rao",
            email="a.rao@contractor.example",
            link_status="unmatched",
            match_reason="Several people match; choose one",
        )
    )
    github = GitHubInstallation(
        tenant_id=access.tenant_id,
        installation_id=SAMPLE_GITHUB_INSTALLATION,
        account_login="northwind-demo",
        account_type="Organization",
        status="active",
        connected_by=access.user_id,
        last_synced_at=NOW - timedelta(hours=2),
        last_sync_status="ok",
    )
    access.session.add(github)
    await access.session.flush()
    await _history(access, ids, github.id, linear.id)


# Commit messages (first lines) behind the sample's pull requests; some name the issue or the
# Linear ticket they belong to, which is how Memory Replay ties the work together.
PR_COMMITS: dict[int, tuple[str, ...]] = {
    14: ("Raise step timeout to 30 minutes", "Log the step that timed out (refs #12)"),
    21: ("Add canary stage", "Route 5% of traffic to the canary", "Canary dashboard link"),
    26: ("Fail promotion on canary 5xx rate", "Alert on blocked promotion (#25)"),
    31: ("Bump runner image to Ubuntu 24.04", "Pin Node 22 in the runner"),
    34: ("Rollback procedure draft", "Add flag cleanup step"),
    38: (
        "Rollback command for payments-api",
        "Keep the previous release warm",
        "Tests for rollback",
    ),
}


# A year of synthetic work on the deploy pipeline, for Project Memory Replay and the
# simulator's open work: (kind, number, title, labels, state, days ago, assignees).
DEPLOY_HISTORY: tuple[tuple[str, int, str, list[str], str, int, list[str]], ...] = (
    ("issue", 12, "Deploys time out on large services", ["bug"], "closed", 330, []),
    ("pull_request", 14, "Raise deploy step timeout (fixes #12)", [], "merged", 328, []),
    (
        "pull_request",
        21,
        "Add canary stage to the payments-api pipeline",
        ["feature"],
        "merged",
        260,
        [],
    ),
    ("issue", 25, "Checkout outage after payments-api release", ["incident"], "closed", 190, []),
    ("pull_request", 26, "Block promotion on canary errors (#25)", [], "merged", 186, []),
    (
        "pull_request",
        31,
        "Upgrade runner image to Ubuntu 24.04",
        ["dependencies"],
        "merged",
        140,
        [],
    ),
    ("pull_request", 34, "Document the rollback procedure", ["docs"], "merged", 95, []),
    ("pull_request", 38, "One-click rollback for payments-api", [], "merged", 48, []),
    ("issue", 41, "Rollback leaves feature flags enabled", ["bug"], "open", 9, ["arjun-nw"]),
    (
        "pull_request",
        42,
        "Move deploy secrets to the new vault path",
        ["security"],
        "open",
        4,
        ["arjun-nw"],
    ),
)
PAYMENTS_ISSUES: tuple[tuple[str, list[str], str, int], ...] = (  # title, labels, state, days
    ("Refund retries create duplicate refunds", ["bug"], "completed", 400),
    ("Idempotency keys on every refund call", [], "completed", 380),
    ("Stripe webhook backlog during the sale", ["incident"], "completed", 75),
    ("Payout reconciliation report", [], "started", 6),
)


async def _history(
    access: WorkspaceAccess,
    ids: dict[str, uuid.UUID],
    github_id: uuid.UUID,
    linear_id: uuid.UUID,
) -> None:
    """Synthetic GitHub, Linear and Notion records: never synced, no tokens."""
    session, tenant = access.session, access.tenant_id
    repo = GitHubRepository(
        id=uuid.uuid7(),
        tenant_id=tenant,
        installation_ref=github_id,
        github_repo_id=990000001,
        full_name="northwind/deploy-pipelines",
        html_url="https://github.com/northwind/deploy-pipelines",
        default_branch="main",
        private=True,
        archived=False,
        audience="workspace",
        responsibility_id=ids["r_deploys"],
        last_synced_at=NOW - timedelta(hours=2),
        pushed_at=NOW - timedelta(days=4),
        last_activity_at=NOW - timedelta(days=4),
    )
    session.add(repo)
    await session.flush()
    for kind, number, title, labels, state, days, assignees in DEPLOY_HISTORY:
        commits = _sample_commits(number, NOW - timedelta(days=days))
        at = NOW - timedelta(days=days)
        path = "pull" if kind == "pull_request" else "issues"
        session.add(
            GitHubWorkItem(
                tenant_id=tenant,
                repository_id=repo.id,
                kind=kind,
                number=number,
                github_id=990000000 + number,
                title=title,
                state=state,
                author_login="leo-nw" if number in (31, 34) else "arjun-nw",
                assignee_logins=assignees,
                labels=labels,
                html_url=f"https://github.com/northwind/deploy-pipelines/{path}/{number}",
                gh_created_at=at - timedelta(days=2),
                gh_updated_at=at,
                closed_at=at if state != "open" else None,
                merged_at=at if state == "merged" else None,
                commits=commits,
            )
        )
    session.add(
        LinearProject(
            tenant_id=tenant,
            connection_ref=linear_id,
            linear_id="demo-proj-payments",
            name="Payments reliability",
            state="started",
            url="https://linear.app/northwind-demo/project/payments-reliability",
            responsibility_id=ids["r_payments"],
            audience="workspace",
        )
    )
    for n, (title, labels, state, days) in enumerate(PAYMENTS_ISSUES, start=101):
        at = NOW - timedelta(days=days)
        session.add(
            LinearIssue(
                tenant_id=tenant,
                connection_ref=linear_id,
                linear_id=f"demo-iss-{n}",
                identifier=f"PAY-{n}",
                title=title,
                state_type=state,
                state_name="Done" if state == "completed" else "In Progress",
                priority=1 if "incident" in labels else 3,
                project_linear_id="demo-proj-payments",
                labels=labels,
                url=f"https://linear.app/northwind-demo/issue/PAY-{n}",
                li_created_at=at - timedelta(days=3),
                li_updated_at=at,
                completed_at=at if state == "completed" else None,
            )
        )
    notion = NotionConnection(
        tenant_id=tenant,
        workspace_id="demo-notion",
        workspace_name="Northwind (demo Notion)",
        status="active",
        connected_by=access.user_id,
        last_synced_at=NOW - timedelta(hours=5),
        last_sync_status="ok",
    )
    session.add(notion)
    await session.flush()
    source = NotionSource(
        tenant_id=tenant,
        connection_ref=notion.id,
        notion_id="demo-notion-release",
        kind="page",
        title="Release management",
        url="https://www.notion.so/northwind-demo/release-management",
        last_edited_at=NOW - timedelta(days=21),
        responsibility_id=ids["r_deploys"],
        visibility="workspace",
        mapped_by=access.user_id,
        mapped_at=NOW - timedelta(days=200),
    )
    session.add(source)
    await session.flush()
    session.add(
        NotionPage(
            tenant_id=tenant,
            source_ref=source.id,
            notion_id="demo-notion-calendar",
            title="Release calendar",
            url="https://www.notion.so/northwind-demo/release-calendar",
            last_edited_at=NOW - timedelta(days=21),
            revision="demo-rev-1",
            knowledge_item_id=ids["release_calendar"],
        )
    )


async def _cases(
    access: WorkspaceAccess,
    ids: dict[str, uuid.UUID],
    users: dict[str, uuid.UUID],
    settings: Settings,
    jobs: procrastinate.App,
) -> uuid.UUID:
    c = cases
    # A completed transfer: vendor contracts moved from Tom to Ines last month.
    done = await c.create_case(
        access,
        c.CaseIn(
            case_type="transfer",
            title="Vendor contracts to Ines",
            starts_at=NOW - timedelta(days=1),
            reason="Tom is focusing on the month-end close.",
        ),
        jobs,
    )
    detail = await c.add_scope_item(
        access, done.id, c.ScopeItemIn(responsibility_id=ids["r_vendors"])
    )
    await c.update_scope_item(
        access,
        done.id,
        detail.scope[0].id,
        c.ScopeItemUpdate(recipient_person_id=ids["p_ines"], handover_notes="Renewals in Q3."),
    )
    await c.submit_case(access, done.id, jobs)
    await c.decide(access, done.id, c.DecisionIn(decision="approved", comment="Agreed"), jobs)
    detail = await c.execute_case(access, done.id, jobs)
    for crit in detail.criteria:
        await c.update_criterion(access, done.id, crit.id, c.CriterionUpdate(status="met"))
    # Ines accepted the handover (recorded by the coordinator) before it was closed.
    await workflow.accept(access, done.id, detail.scope[0].id, jobs)
    await c.complete_case(access, done.id, jobs)

    # The live scenario: Arjun is leaving; Relay discovers what he holds.
    departure = await c.create_case(
        access,
        c.CaseIn(
            case_type="departure",
            title="Arjun Rao is leaving Platform",
            affected_person_id=ids["p_arjun"],
            starts_at=NOW + timedelta(days=14),
            due_at=NOW + timedelta(days=12),
            priority="high",
            reason="Last day in two weeks; deployments and on-call need new owners.",
            accountable_manager_user_id=users["demo_maya"],
        ),
        jobs,
    )
    scope = {s.responsibility_id: s.id for s in departure.scope}
    await c.update_scope_item(
        access,
        departure.id,
        scope[ids["r_deploys"]],
        c.ScopeItemUpdate(recipient_person_id=ids["p_dev"], handover_notes="Pair on two deploys."),
    )
    await c.add_task(
        access,
        departure.id,
        c.TaskIn(
            title="Walk Dev through a canary deploy",
            assignee_user_id=users["demo_arjun"],
            due_at=NOW + timedelta(days=5),
            priority="high",
        ),
        jobs,
    )
    await c.add_task(
        access,
        departure.id,
        c.TaskIn(title="Record the rollback procedure", assignee_user_id=users["demo_arjun"]),
        jobs,
    )
    await workflow.add_blocker(
        access,
        departure.id,
        workflow.BlockerIn(
            description="Dev doesn't have production deploy access yet",
            owner_user_id=users["demo_maya"],
        ),
        jobs,
    )
    await runs.start_analysis(access, departure.id, settings, jobs)
    await interviews.generate(access, departure.id, settings, jobs)

    # Planned cover while Priya is away (overlaps nothing; Sara covers).
    cover = await c.create_case(
        access,
        c.CaseIn(
            case_type="coverage",
            title="Priya on leave",
            affected_person_id=ids["p_priya"],
            starts_at=NOW + timedelta(days=20),
            ends_at=NOW + timedelta(days=34),
        ),
        jobs,
    )
    for item in cover.scope:
        await c.update_scope_item(
            access, cover.id, item.id, c.ScopeItemUpdate(recipient_person_id=ids["p_sara"])
        )
    return departure.id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--owner", required=True, help="WorkOS user id of the demo owner")
    args = parser.parse_args()
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    tenant = asyncio.run(seed(args.owner), loop_factory=loop_factory)
    print(f"Demo workspace created: {tenant}")


MEETINGS = (
    (
        "Arjun handover kickoff",
        "deploys",
        True,
        5,
        """Maya: Thanks for joining. Arjun's last day is on the 28th, so let's plan the handover.
Arjun: The deploy pipeline is mostly documented, but the rollback for billing-db is not.
Maya: We decided Dev takes over production deployments, with Sara as backup.
Arjun: I'll record a walkthrough of the canary release by Thursday.
Dev: Can you share the access list for the deploy-pipelines repo?
Arjun: Yes. Dev will pair with me on the next two Friday deploys.
Sara: Only Arjun knows the manual steps for the legacy SFTP bridge, that's a risk.
Maya: Who approves an emergency rollback if both Dev and Sara are out?
Arjun: Agreed that we freeze non-urgent deploys during the last week of the quarter.
Maya: Tom will update the on-call rota by Monday.
Dev: Is the Terraform state for staging still in the old bucket?
Maya: Great, thanks everyone.""",
    ),
    (
        "Refund double-charge incident review",
        "payments",
        False,
        12,
        """Priya: This review covers the duplicate refunds on the 3rd.
Leo: Root cause was a retry on the Stripe webhook without an idempotency key.
Priya: We decided to require idempotency keys on every refund call from now on.
Leo: I'll add the idempotency check to payments-api by Friday.
Ines: Please document the refund reconciliation steps in the runbook.
Priya: The reconciliation job alerts go to Arjun's personal email, that's a blocker once he leaves.
Leo: Final call: refunds above 50k need a second approver.
Ines: Who owns the Stripe account after Arjun leaves?
Priya: Ines will draft the customer comms template by next week.""",
    ),
    (
        "Platform weekly sync",
        "oncall",
        False,
        19,
        """Maya: Quick sync. On-call load is up 30 percent this month.
Sara: Most pages are the billing-db disk alerts.
Maya: We agreed to raise the disk alert threshold to 85 percent.
Sara: I'll write the disk cleanup procedure by Wednesday.
Dev: Are we still paying for the old PagerDuty seats?
Maya: Concern: we have no second person who can restore billing-db from backup.
Tom: Leo will shadow Sara on two restore drills next week.""",
    ),
)


async def _meetings(
    access: WorkspaceAccess,
    ids: dict[str, uuid.UUID],
    departure: uuid.UUID,
    settings: Settings,
    jobs: procrastinate.App,
) -> None:
    """Three recent meetings, read by rules; a few items already accepted so the decision
    log and the case's tasks show the result, and the rest wait for review."""
    for title, resp, on_case, days, transcript in MEETINGS:
        made = await meetings.create_meeting(
            access,
            meetings.MeetingIn(
                title=title,
                held_at=NOW - timedelta(days=days),
                transcript=transcript,
                responsibility_id=ids[f"r_{resp}"],
                case_id=departure if on_case else None,
            ),
            settings,
            use_ai=False,
        )
        decisions = [i for i in made.items if i.kind == "decision"]
        actions = [i for i in made.items if i.kind == "action"]
        for item in [*decisions[:1], *actions[:1]]:
            await meetings.review_item(access, item.id, True, jobs)
    # The old runbook was last checked months ago; merges since then flag it as code drift.
    long_ago = NOW - timedelta(days=200)
    await access.session.execute(
        update(KnowledgeItem)
        .where(KnowledgeItem.title == "Deploy payments-api (old runbook)")
        .values(updated_at=long_ago, last_reviewed_at=long_ago)
    )


# ---------------------------------------------------------------- judges' shared workspace

JUDGES_NAME = "Northwind Labs (judges)"


def parse_accounts(spec: str) -> dict[str, tuple[str, str | None]]:
    """`owner:a@x.com,admin:b@x.com=user_01...` -> {role: (email, WorkOS id or None)}.

    Every role must be a real role. A WorkOS id after `=` skips the lookup, so the seed can run
    where the WorkOS API key isn't available (e.g. CI).
    """
    accounts: dict[str, tuple[str, str | None]] = {}
    for part in filter(None, (p.strip() for p in spec.split(","))):
        role, _, rest = part.partition(":")
        email, _, workos_id = rest.partition("=")
        if role not in ROLE_PERMISSIONS or "@" not in email:
            raise ValueError(f"not a role:email pair: {part!r}")
        accounts[role] = (email.strip().lower(), workos_id.strip() or None)
    if "owner" not in accounts:
        raise ValueError("an owner account is required")
    return accounts


async def seed_judges(spec: str) -> uuid.UUID:
    """One shared sample with a real sign-in for each role. The accounts must already exist
    in WorkOS (created with passwords by a person); this only looks them up by email."""
    accounts = parse_accounts(spec)
    settings = Settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    jobs = create_job_app(settings, factory)
    try:
        users: dict[str, WorkOSUser] = {}
        async with httpx.AsyncClient(timeout=20) as http:
            client = WorkOSClient(settings, http)
            for role, (email, workos_id) in accounts.items():
                found = (
                    WorkOSUser(id=workos_id, email=email, email_verified=True, display_name=None)
                    if workos_id
                    else await client.find_user_by_email(email)
                )
                if found is None:
                    raise SystemExit(f"No WorkOS user for {email}: create it first.")
                users[role] = found
        async with jobs.open_async():
            ws, _ = await seed_workspace(
                users["owner"].id,
                settings,
                factory,
                jobs,
                idempotency_key=f"judges-{users['owner'].id}",
                name=JUDGES_NAME,
            )
        # Workspaces seeded before the sample's GitHub connection was healthy show it as synced.
        async with unit_of_work(factory, ws.id, users["owner"].id) as session:
            await session.execute(
                update(GitHubInstallation)
                .where(
                    GitHubInstallation.tenant_id == ws.id,
                    GitHubInstallation.installation_id == SAMPLE_GITHUB_INSTALLATION,
                )
                .values(last_sync_status="ok", last_sync_error=None)
            )
        async with open_workspace_access(factory, _identity(users["owner"].id), ws.id) as access:
            await _dependencies(access)
            await _backfill_commits(access)
        # Each role account *is* that role's sample person: the person's directory email becomes
        # the account's email, so its My Work and "Accept ownership" are real, while the
        # membership keeps the account's own address, so Relay's emails reach whoever signed in.
        personas: dict[str, str] = {}
        for name_role, name in MEMBERS.values():
            personas.setdefault(name_role, name)
        for role, user in users.items():
            if role == "owner":
                continue
            persona = personas.get(role)
            persona_email = f"{persona.split()[0].lower()}@{DOMAIN}" if persona else None
            email = user.email
            display = f"{persona} (sample account)" if persona else user.email.split("@")[0]
            async with unit_of_work(factory, ws.id, user.id) as session:
                user_id = (
                    await session.execute(
                        insert(UserAccount)
                        .values(workos_user_id=user.id)
                        .on_conflict_do_update(
                            index_elements=["workos_user_id"], set_={"workos_user_id": user.id}
                        )
                        .returning(UserAccount.id)
                    )
                ).scalar_one()
                await session.execute(
                    insert(Membership)
                    .values(
                        tenant_id=ws.id,
                        user_id=user_id,
                        role=role,
                        status="active",
                        display_name=display,
                        email=email,
                        member_type="contractor" if role == "guest" else "employee",
                    )
                    .on_conflict_do_update(
                        index_elements=["tenant_id", "user_id"],
                        set_={"role": role, "email": email, "display_name": display},
                    )
                )
                if persona_email:
                    await session.execute(
                        update(Person)
                        .where(func.lower(Person.email) == persona_email)
                        .values(email=email)
                    )
        return ws.id
    finally:
        await engine.dispose()


def judges_main() -> None:
    parser = argparse.ArgumentParser(description="Seed the judges' shared sample workspace.")
    parser.add_argument(
        "--accounts",
        default=os.environ.get("RELAY_JUDGE_ACCOUNTS", ""),
        help="role:email pairs, comma separated (or RELAY_JUDGE_ACCOUNTS)",
    )
    args = parser.parse_args()
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    tenant = asyncio.run(seed_judges(args.accounts), loop_factory=loop_factory)
    print(f"Judges' workspace ready: {tenant}")


if __name__ == "__main__":
    main()
