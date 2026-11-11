"""Seed a synthetic demo organisation: `uv run relay-demo-seed --owner <workos_user_id>`.

Also used by `POST /workspaces/sample` (relay.demo.api) so a new user can explore Relay
without connecting real sources. Creates a NEW workspace ("Northwind Labs (demo)") each
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

import argparse
import asyncio
import sys
import uuid
from datetime import UTC, datetime, timedelta

import procrastinate
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from relay.catalog import assets as catalog_assets
from relay.catalog import knowledge
from relay.catalog import service as catalog
from relay.catalog.models import KnowledgeItem
from relay.config import Settings
from relay.continuity import service as cases
from relay.continuity import workflow
from relay.directory import service as directory
from relay.identity.models import Membership, UserAccount
from relay.identity.tokens import VerifiedIdentity
from relay.identity.workspace_access import WorkspaceAccess, open_workspace_access
from relay.integrations.github.models import GitHubInstallation
from relay.integrations.linear.models import LinearConnection, LinearIdentity
from relay.intelligence import capsules, interviews, runs
from relay.jobs.app import create_job_app
from relay.platform import workspaces
from relay.platform.workspaces import WorkspaceView
from relay.shared.db import create_engine, create_session_factory, unit_of_work

NOW = datetime.now(UTC)
SAMPLE_NAME = "Northwind Labs (demo)"
DOMAIN = "northwind.example"  # reserved for documentation: never a real mailbox
MEMBERS = {  # synthetic member id -> (role, display name)
    "demo_maya": ("admin", "Maya Chen"),
    "demo_tom": ("continuity_manager", "Tom Okafor"),
    "demo_priya": ("member", "Priya Nair"),
    "demo_arjun": ("member", "Arjun Rao"),
    "demo_sara": ("member", "Sara Kim"),
    "demo_ines": ("knowledge_steward", "Ines Duarte"),
    "demo_leo": ("member", "Leo Martins"),
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
) -> tuple[WorkspaceView, bool]:
    """Create and populate a sample workspace owned by `owner`.

    Returns (workspace, created). Replaying the same idempotency key returns the original
    workspace without seeding it a second time.
    """
    ws, created = await workspaces.create_workspace(
        factory, jobs, _identity(owner), SAMPLE_NAME, idempotency_key or f"demo-{uuid.uuid7()}"
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
                    member_type="contractor" if sub == "demo_leo" else "employee",
                )
            )
            users[sub] = user_id

    async with open_workspace_access(factory, _identity(owner), tenant) as access:
        ids = await _catalog(access, users)
    async with open_workspace_access(factory, _identity(owner), tenant) as access:
        await _connectors(access, ids)
    async with open_workspace_access(factory, _identity(owner), tenant) as access:
        departure = await _cases(access, ids, users, settings, jobs)
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
    access.session.add(
        KnowledgeItem(
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
        "team_platform": platform.id,
    }


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
    access.session.add(
        GitHubInstallation(  # the deliberate failure path: access was lost
            tenant_id=access.tenant_id,
            installation_id=999000001,
            account_login="northwind-demo",
            account_type="Organization",
            status="active",
            connected_by=access.user_id,
            last_synced_at=NOW - timedelta(hours=2),
            last_sync_status="error",
            last_sync_error="GitHub returned 403: the app lost access to some repositories",
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


if __name__ == "__main__":
    main()
