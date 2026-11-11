""" "What if?" continuity simulator: the impact of one person becoming unavailable.

Read-only by construction: it reads current ownership, knowledge, open work and risks the
caller may see, and recomputes coverage in memory as if the person were gone (and, if a
backup is named, as if that backup took over whatever would be left uncovered). Nothing
is written; closing the simulator leaves the workspace exactly as it was.

The readiness score is deliberately simple and explained in the response, so a manager
can see why it moved: per affected responsibility, weighted by criticality,
cover counts 60%, usable (non-stale) knowledge 25%, and a second holder remaining 15%.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import ColumnElement, and_, func, or_, select

from relay.catalog.knowledge import readable as knowledge_readable
from relay.catalog.knowledge import review_cutoff
from relay.catalog.models import (
    Asset,
    KnowledgeItem,
    OwnershipAssignment,
    Responsibility,
    ResponsibilityAsset,
)
from relay.continuity.models import OPEN_STATUSES, CaseScopeItem, CaseTask, ContinuityCase
from relay.directory.models import Person, Team, TeamMember
from relay.directory.profiles import RiskRef, _member_user, _risks
from relay.identity.workspace_access import WorkspaceAccess
from relay.integrations.audience import linear_issue_shared, shared
from relay.integrations.github.models import GitHubRepository, GitHubWorkItem
from relay.integrations.linear.models import LinearIdentity, LinearIssue, LinearProject
from relay.policy.permissions import Permission, authorize, visible
from relay.shared.errors import ApiError

WEIGHT = {"critical": 4, "high": 3, "standard": 2, "low": 1}
ROLE_ORDER = {"primary": 0, "co_owner": 1, "temporary": 2, "backup": 3}
SCORE_BASIS = (
    "Per affected responsibility, weighted by criticality (critical 4, high 3, standard 2, "
    "low 1): someone else covers it 60%, it has knowledge that is not stale 25%, and more "
    "than one holder remains 15%."
)
MAX_OPEN_WORK = 25

Cover = Literal["covered", "covered_by_backup", "uncovered"]


class Holder(BaseModel):
    name: str
    role: str
    kind: Literal["person", "team"]


class SimulatedResponsibility(BaseModel):
    responsibility_id: uuid.UUID
    name: str
    criticality: str
    role: str  # what the person holds today
    cover: Cover
    covered_by: Holder | None
    remaining_holders: list[Holder]
    knowledge_total: int
    knowledge_stale: int
    single_holder_after: bool
    assets: list[str] = []  # what it stewards: assets are reached through responsibilities
    # Why it is affected and how exposed it is, each read from a record (no inference).
    reasons: list[str] = []


class OpenWork(BaseModel):
    source: Literal["Relay task", "GitHub", "Linear"]
    title: str
    url: str | None
    responsibility_name: str | None = None
    due_at: datetime | None = None
    due_in_window: bool = False  # falls due while the person is away


class ExposedRisk(BaseModel):
    kind: Literal["uncovered", "single_holder", "undocumented", "stale_knowledge"]
    severity: Literal["high", "medium", "low"]
    responsibility_id: uuid.UUID
    responsibility_name: str
    detail: str


class PersonRef(BaseModel):
    id: uuid.UUID
    name: str
    title: str | None


class BackupLoad(BaseModel):
    current_responsibilities: int
    would_take_over: int


class SimulationView(BaseModel):
    person: PersonRef
    backup: PersonRef | None
    affected_responsibilities: list[SimulatedResponsibility]
    covered_by_backup: list[uuid.UUID]
    uncovered_responsibilities: list[uuid.UUID]
    orphaned_knowledge_count: int
    open_work_without_cover: list[OpenWork]
    open_work_total: int
    existing_risks: list[RiskRef]
    exposed_risks: list[ExposedRisk]
    baseline_score: int  # without the backup (equal to readiness_score when none is named)
    readiness_score: int
    score_basis: str
    backup_load: BackupLoad | None
    simulated_at: datetime
    days: int | None = None  # how long the person is away, if given
    affected_assets: list[str] = []
    due_in_window: int = 0


class Candidate(BaseModel):
    person: PersonRef | None  # None: nobody steps in
    signals: list[str]  # deterministic reasons this person could cover; no scores
    covered: int  # affected responsibilities someone would hold
    total: int
    critical_gaps: int  # critical or high responsibilities left with nobody
    knowledge_gaps: int  # affected responsibilities with no usable knowledge
    remaining_risks: int
    readiness_score: int
    load_after: int | None  # responsibilities they would hold, including the takeover


class CandidatesView(BaseModel):
    person: PersonRef
    candidates: list[Candidate]
    basis: str


async def _person(access: WorkspaceAccess, person_id: uuid.UUID, what: str) -> Person:
    person = await access.session.scalar(
        select(Person).where(
            Person.id == person_id, visible(access, Permission.DIRECTORY_READ, Person.tenant_id)
        )
    )
    if person is None:
        raise ApiError(404, "not_found", f"{what} not found.")
    return person


def _ref(p: Person) -> PersonRef:
    return PersonRef(id=p.id, name=p.display_name, title=p.title)


def _current(now: datetime) -> list[ColumnElement[bool]]:
    return [
        OwnershipAssignment.valid_from <= now,
        or_(OwnershipAssignment.valid_to.is_(None), OwnershipAssignment.valid_to > now),
    ]


async def _team_members(
    access: WorkspaceAccess, team_ids: set[uuid.UUID]
) -> dict[uuid.UUID, set[uuid.UUID]]:
    members: dict[uuid.UUID, set[uuid.UUID]] = {t: set() for t in team_ids}
    if team_ids:
        for team_id, person_id in await access.session.execute(
            select(TeamMember.team_id, TeamMember.person_id)
            .join(Person, Person.id == TeamMember.person_id)
            .where(
                visible(access, Permission.DIRECTORY_READ, TeamMember.tenant_id),
                TeamMember.team_id.in_(team_ids),
                Person.status == "active",
            )
        ):
            members[team_id].add(person_id)
    return members


async def simulate(
    access: WorkspaceAccess,
    person_id: uuid.UUID,
    backup_id: uuid.UUID | None = None,
    days: int | None = None,
) -> SimulationView:
    authorize(access, Permission.CONTINUITY_SIMULATE)
    session, now = access.session, datetime.now(UTC)
    person = await _person(access, person_id, "Person")
    backup = await _person(access, backup_id, "Backup") if backup_id else None
    if backup is not None and backup.id == person.id:
        raise ApiError(422, "backup_is_person", "Choose a backup other than the person.")

    my_teams = set(
        await session.scalars(select(TeamMember.team_id).where(TeamMember.person_id == person.id))
    )
    rows = list(
        await session.execute(
            select(OwnershipAssignment, Responsibility)
            .join(Responsibility, Responsibility.id == OwnershipAssignment.responsibility_id)
            .where(
                visible(access, Permission.RESPONSIBILITY_READ, OwnershipAssignment.tenant_id),
                Responsibility.status == "active",
                *_current(now),
            )
        )
    )
    by_resp: dict[uuid.UUID, tuple[Responsibility, list[OwnershipAssignment]]] = {}
    for a, r in rows:
        by_resp.setdefault(r.id, (r, []))[1].append(a)
    team_ids = {a.team_id for a, _ in rows if a.team_id}
    members = await _team_members(access, team_ids)
    names = {
        **dict((await session.execute(select(Person.id, Person.display_name))).all()),
        **dict((await session.execute(select(Team.id, Team.name))).all()),
    }

    def holds(a: OwnershipAssignment) -> bool:
        """The person holds this role directly, or through a team only they are left in."""
        if a.person_id == person.id:
            return True
        return a.team_id in my_teams and not (members.get(a.team_id, set()) - {person.id})

    affected: list[SimulatedResponsibility] = []
    responsibility_ids: list[uuid.UUID] = []
    for rid, (resp, assignments) in by_resp.items():
        mine = [a for a in assignments if holds(a)]
        if not mine:
            continue
        responsibility_ids.append(rid)
        remaining = sorted(
            (a for a in assignments if not holds(a)), key=lambda a: ROLE_ORDER.get(a.role, 9)
        )
        holders = [
            Holder(
                name=names.get(a.person_id or a.team_id, "Unknown"),  # type: ignore[arg-type]
                role=a.role,
                kind="person" if a.person_id else "team",
            )
            for a in remaining
        ]
        distinct = {a.person_id or a.team_id for a in remaining}
        cover: Cover = "covered" if holders else "uncovered"
        covered_by = holders[0] if holders else None
        if cover == "uncovered" and backup is not None:
            cover = "covered_by_backup"
            covered_by = Holder(name=backup.display_name, role="temporary", kind="person")
            distinct.add(backup.id)
        affected.append(
            SimulatedResponsibility(
                responsibility_id=rid,
                name=resp.name,
                criticality=resp.criticality,
                role=min((a.role for a in mine), key=lambda r: ROLE_ORDER.get(r, 9)),
                cover=cover,
                covered_by=covered_by,
                remaining_holders=holders,
                knowledge_total=0,
                knowledge_stale=0,
                single_holder_after=len(distinct) <= 1,
            )
        )

    await _knowledge_counts(access, affected)
    await _explain(access, affected, person.display_name, now)
    affected.sort(key=lambda s: (-WEIGHT.get(s.criticality, 1), s.cover != "uncovered", s.name))
    exposed = _exposed(affected)
    open_work = await _open_work(access, person, set(responsibility_ids))
    until = now + timedelta(days=days) if days else None
    for w in open_work:
        w.due_in_window = bool(until and w.due_at and w.due_at <= until)
    without_cover = [
        w
        for w in open_work
        if w.responsibility_name is None
        or any(s.name == w.responsibility_name and s.cover == "uncovered" for s in affected)
    ]
    backup_load = None
    if backup is not None:
        held = await session.scalar(
            select(func.count(func.distinct(OwnershipAssignment.responsibility_id))).where(
                visible(access, Permission.RESPONSIBILITY_READ, OwnershipAssignment.tenant_id),
                OwnershipAssignment.person_id == backup.id,
                *_current(now),
            )
        )
        backup_load = BackupLoad(
            current_responsibilities=held or 0,
            would_take_over=sum(1 for s in affected if s.cover == "covered_by_backup"),
        )
    return SimulationView(
        person=_ref(person),
        backup=_ref(backup) if backup else None,
        affected_responsibilities=affected,
        covered_by_backup=[s.responsibility_id for s in affected if s.cover == "covered_by_backup"],
        uncovered_responsibilities=[
            s.responsibility_id for s in affected if s.cover == "uncovered"
        ],
        orphaned_knowledge_count=await _orphaned_knowledge(access, person),
        open_work_without_cover=without_cover[:MAX_OPEN_WORK],
        open_work_total=len(open_work),
        existing_risks=await _risks(access, set(responsibility_ids), {person.id}),
        exposed_risks=exposed,
        baseline_score=_score(affected, with_backup=False),
        readiness_score=_score(affected, with_backup=True),
        score_basis=SCORE_BASIS,
        backup_load=backup_load,
        simulated_at=now,
        days=days,
        affected_assets=sorted({a for s in affected for a in s.assets}),
        due_in_window=sum(1 for w in open_work if w.due_in_window),
    )


async def _knowledge_counts(
    access: WorkspaceAccess, affected: list[SimulatedResponsibility]
) -> None:
    if not affected:
        return
    cutoff = await review_cutoff(access)
    reviewed = func.coalesce(KnowledgeItem.last_reviewed_at, KnowledgeItem.created_at)
    stale = or_(
        and_(KnowledgeItem.origin != "person", KnowledgeItem.last_reviewed_at.is_(None)),
        reviewed < cutoff,
    )
    counts = {
        rid: (total, n_stale)
        for rid, total, n_stale in await access.session.execute(
            select(
                KnowledgeItem.responsibility_id,
                func.count(),
                func.count().filter(stale),
            )
            .where(
                knowledge_readable(access),
                KnowledgeItem.status == "active",
                KnowledgeItem.responsibility_id.in_([s.responsibility_id for s in affected]),
            )
            .group_by(KnowledgeItem.responsibility_id)
        )
    }
    for s in affected:
        s.knowledge_total, s.knowledge_stale = counts.get(s.responsibility_id, (0, 0))


def _exposed(affected: list[SimulatedResponsibility]) -> list[ExposedRisk]:
    out = []
    for s in affected:
        important = s.criticality in ("critical", "high")
        if s.cover == "uncovered":
            out.append(
                ExposedRisk(
                    kind="uncovered",
                    severity="high" if important else "medium",
                    responsibility_id=s.responsibility_id,
                    responsibility_name=s.name,
                    detail="Nobody else holds this responsibility.",
                )
            )
        elif s.single_holder_after:
            who = s.covered_by.name if s.covered_by else "one holder"
            out.append(
                ExposedRisk(
                    kind="single_holder",
                    severity="medium" if important else "low",
                    responsibility_id=s.responsibility_id,
                    responsibility_name=s.name,
                    detail=f"Only {who} would be left: a new single-person dependency.",
                )
            )
        if s.knowledge_total == 0:
            out.append(
                ExposedRisk(
                    kind="undocumented",
                    severity="high" if important else "medium",
                    responsibility_id=s.responsibility_id,
                    responsibility_name=s.name,
                    detail="No recorded knowledge: whoever takes over starts from nothing.",
                )
            )
        elif s.knowledge_stale == s.knowledge_total:
            out.append(
                ExposedRisk(
                    kind="stale_knowledge",
                    severity="medium" if important else "low",
                    responsibility_id=s.responsibility_id,
                    responsibility_name=s.name,
                    detail=f"All {s.knowledge_total} knowledge items are due for review.",
                )
            )
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(out, key=lambda e: (order[e.severity], e.responsibility_name))


def _score(affected: list[SimulatedResponsibility], *, with_backup: bool) -> int:
    if not affected:
        return 100
    total = earned = 0.0
    for s in affected:
        w = WEIGHT.get(s.criticality, 1)
        covered = s.cover == "covered" or (with_backup and s.cover == "covered_by_backup")
        documented = s.knowledge_total > s.knowledge_stale
        # Without the backup, a responsibility the backup would cover has no holder at all.
        resilient = not s.single_holder_after and (with_backup or s.cover == "covered")
        total += w
        earned += w * (0.60 * covered + 0.25 * documented + 0.15 * resilient)
    return round(100 * earned / total)


async def _orphaned_knowledge(access: WorkspaceAccess, person: Person) -> int:
    """Active knowledge the person wrote or stewards: it loses its keeper."""
    user_id = await _member_user(access, person)
    if user_id is None:
        return 0
    return (
        await access.session.scalar(
            select(func.count()).where(
                knowledge_readable(access),
                KnowledgeItem.status == "active",
                or_(
                    KnowledgeItem.author_user_id == user_id,
                    KnowledgeItem.steward_user_id == user_id,
                ),
            )
        )
        or 0
    )


async def _open_work(
    access: WorkspaceAccess, person: Person, responsibility_ids: set[uuid.UUID]
) -> list[OpenWork]:
    """Open case tasks, GitHub pull requests/issues and Linear issues assigned to them."""
    session = access.session
    work: list[OpenWork] = []
    user_id = await _member_user(access, person)
    if user_id is not None:
        for title, case_title, due_at in await session.execute(
            select(CaseTask.title, ContinuityCase.title, CaseTask.due_at)
            .join(ContinuityCase, ContinuityCase.id == CaseTask.case_id)
            .where(
                visible(access, Permission.CASE_READ, CaseTask.tenant_id),
                CaseTask.assignee_user_id == user_id,
                CaseTask.status == "open",
                ContinuityCase.status.in_(OPEN_STATUSES),
            )
            .order_by(CaseTask.due_at.asc().nulls_last())
            .limit(MAX_OPEN_WORK)
        ):
            work.append(
                OpenWork(
                    source="Relay task", title=f"{title} ({case_title})", url=None, due_at=due_at
                )
            )
    resp_names = dict(
        (
            await session.execute(
                select(Responsibility.id, Responsibility.name).where(
                    Responsibility.id.in_(responsibility_ids)
                )
            )
        ).all()
    )
    if person.github_login:
        for item, rid in await session.execute(
            select(GitHubWorkItem, GitHubRepository.responsibility_id)
            .join(GitHubRepository, GitHubRepository.id == GitHubWorkItem.repository_id)
            .where(
                visible(access, Permission.RESPONSIBILITY_READ, GitHubWorkItem.tenant_id),
                shared(access, GitHubRepository.audience),
                GitHubWorkItem.state == "open",
                GitHubWorkItem.assignee_logins.contains([person.github_login]),
            )
            .order_by(GitHubWorkItem.gh_updated_at.desc())
            .limit(MAX_OPEN_WORK)
        ):
            work.append(
                OpenWork(
                    source="GitHub",
                    title=item.title,
                    url=item.html_url,
                    responsibility_name=resp_names.get(rid) if rid else None,
                )
            )
    linear_ids = list(
        await session.scalars(
            select(LinearIdentity.linear_id).where(LinearIdentity.person_id == person.id)
        )
    )
    if linear_ids:
        for issue in await session.scalars(
            select(LinearIssue)
            .where(
                visible(access, Permission.RESPONSIBILITY_READ, LinearIssue.tenant_id),
                linear_issue_shared(access),
                LinearIssue.assignee_linear_id.in_(linear_ids),
                LinearIssue.state_type.notin_(("completed", "canceled")),
            )
            .order_by(LinearIssue.li_updated_at.desc())
            .limit(MAX_OPEN_WORK)
        ):
            work.append(
                OpenWork(source="Linear", title=f"{issue.identifier} {issue.title}", url=issue.url)
            )
    return work


ROLE_WORDS = {"primary": "primary owner", "co_owner": "co-owner", "backup": "backup"}
RECENT = timedelta(days=30)


async def _explain(
    access: WorkspaceAccess, affected: list[SimulatedResponsibility], who: str, now: datetime
) -> None:
    """Assets and plain reasons per affected responsibility, read from records."""
    if not affected:
        return
    session = access.session
    ids = [s.responsibility_id for s in affected]
    readable = Permission.RESPONSIBILITY_READ
    assets: dict[uuid.UUID, list[str]] = {}
    for rid, name in await session.execute(
        select(ResponsibilityAsset.responsibility_id, Asset.name)
        .join(Asset, Asset.id == ResponsibilityAsset.asset_id)
        .where(
            visible(access, readable, Asset.tenant_id),
            ResponsibilityAsset.responsibility_id.in_(ids),
        )
        .order_by(Asset.name)
    ):
        assets.setdefault(rid, []).append(name)
    activity: dict[uuid.UUID | None, list[str]] = {}
    for repo_rid, repo, n in await session.execute(
        select(GitHubRepository.responsibility_id, GitHubRepository.full_name, func.count())
        .join(GitHubWorkItem, GitHubWorkItem.repository_id == GitHubRepository.id)
        .where(
            visible(access, readable, GitHubRepository.tenant_id),
            shared(access, GitHubRepository.audience),
            GitHubRepository.responsibility_id.in_(ids),
            GitHubWorkItem.gh_updated_at >= now - RECENT,
        )
        .group_by(GitHubRepository.responsibility_id, GitHubRepository.full_name)
    ):
        activity.setdefault(repo_rid, []).append(
            f"{n} pull request{'s' if n != 1 else ''} or issue{'s' if n != 1 else ''} "
            f"active in {repo} in the last 30 days"
        )
    for project_rid, project, n in await session.execute(
        select(LinearProject.responsibility_id, LinearProject.name, func.count())
        .join(LinearIssue, LinearIssue.project_linear_id == LinearProject.linear_id)
        .where(
            visible(access, readable, LinearProject.tenant_id),
            shared(access, LinearProject.audience),
            LinearProject.removed.is_(False),
            LinearProject.responsibility_id.in_(ids),
            LinearIssue.state_type.notin_(("completed", "canceled")),
        )
        .group_by(LinearProject.responsibility_id, LinearProject.name)
    ):
        activity.setdefault(project_rid, []).append(
            f"{n} open Linear issue{'s' if n != 1 else ''} in {project}"
        )
    for s in affected:
        s.assets = assets.get(s.responsibility_id, [])
        reasons = [f"{who} is {ROLE_WORDS.get(s.role, s.role)}."]
        if s.cover == "uncovered":
            reasons.append("Nobody else holds it.")
        elif s.cover == "covered_by_backup" and s.covered_by:
            reasons.append(f"Only the simulated cover, {s.covered_by.name}, would hold it.")
        elif s.single_holder_after and s.covered_by:
            reasons.append(f"Only {s.covered_by.name} would be left.")
        if s.knowledge_total == 0:
            reasons.append("No knowledge is recorded for it.")
        elif s.knowledge_stale == s.knowledge_total:
            reasons.append(f"All {s.knowledge_total} knowledge items are due for review.")
        if s.assets:
            reasons.append(f"It looks after {', '.join(s.assets)}.")
        reasons += [f"{a}." for a in activity.get(s.responsibility_id, [])]
        s.reasons = reasons


CANDIDATE_BASIS = (
    "Candidates are people already connected to the affected work: they are its planned "
    "recipient, hold another role on it, share a team with the person, or work in the same "
    "department. People linked to work that would otherwise have nobody come first. Each is "
    "simulated taking over that work. No ranking model is involved."
)
MAX_CANDIDATES = 4


async def candidates(
    access: WorkspaceAccess, person_id: uuid.UUID, days: int | None = None
) -> CandidatesView:
    """Who could cover, by deterministic signals, each compared against nobody stepping in."""
    authorize(access, Permission.CONTINUITY_SIMULATE)
    session, now = access.session, datetime.now(UTC)
    person = await _person(access, person_id, "Person")
    baseline = await simulate(access, person_id, None, days)
    affected_ids = [s.responsibility_id for s in baseline.affected_responsibilities]
    gaps = set(baseline.uncovered_responsibilities)
    signals: dict[uuid.UUID, list[str]] = {}
    weight: dict[uuid.UUID, int] = {}
    on_gaps: dict[uuid.UUID, int] = {}  # links to work that would otherwise have nobody

    def add(pid: uuid.UUID | None, text: str, w: int, rid: uuid.UUID | None = None) -> None:
        if pid is None or pid == person.id:
            return
        if text not in signals.setdefault(pid, []):
            signals[pid].append(text)
            weight[pid] = weight.get(pid, 0) + w
            on_gaps[pid] = on_gaps.get(pid, 0) + (rid in gaps)

    if affected_ids:
        names = dict(
            (
                await session.execute(
                    select(Responsibility.id, Responsibility.name).where(
                        Responsibility.id.in_(affected_ids)
                    )
                )
            ).all()
        )
        for a in await session.scalars(
            select(OwnershipAssignment).where(
                visible(access, Permission.RESPONSIBILITY_READ, OwnershipAssignment.tenant_id),
                OwnershipAssignment.responsibility_id.in_(affected_ids),
                OwnershipAssignment.person_id.is_not(None),
                *_current(now),
            )
        ):
            add(
                a.person_id,
                f"Already {ROLE_WORDS.get(a.role, a.role)} of {names[a.responsibility_id]}",
                3,
                a.responsibility_id,
            )
    if affected_ids:
        for pid, rid in await session.execute(
            select(CaseScopeItem.recipient_person_id, CaseScopeItem.responsibility_id)
            .join(ContinuityCase, ContinuityCase.id == CaseScopeItem.case_id)
            .where(
                visible(access, Permission.CASE_READ, ContinuityCase.tenant_id),
                ContinuityCase.status.in_(OPEN_STATUSES),
                CaseScopeItem.responsibility_id.in_(affected_ids),
                CaseScopeItem.recipient_person_id.is_not(None),
            )
        ):
            add(pid, f"Planned recipient of {names[rid]} in an open handover", 4, rid)
    my_teams = list(
        await session.scalars(select(TeamMember.team_id).where(TeamMember.person_id == person.id))
    )
    if my_teams:
        for pid, team in await session.execute(
            select(TeamMember.person_id, Team.name)
            .join(Team, Team.id == TeamMember.team_id)
            .where(
                visible(access, Permission.DIRECTORY_READ, TeamMember.tenant_id),
                TeamMember.team_id.in_(my_teams),
            )
        ):
            add(pid, f"Same team ({team})", 2)
    if person.department_id:
        for pid in await session.scalars(
            select(Person.id).where(
                visible(access, Permission.DIRECTORY_READ, Person.tenant_id),
                Person.department_id == person.department_id,
                Person.status == "active",
            )
        ):
            add(pid, "Same department", 1)
    active = set(
        await session.scalars(
            select(Person.id).where(
                visible(access, Permission.DIRECTORY_READ, Person.tenant_id),
                Person.status == "active",
            )
        )
    )
    ranked = sorted(
        (pid for pid in signals if pid in active),
        key=lambda pid: (-on_gaps[pid], -weight[pid], str(pid)),
    )[:MAX_CANDIDATES]

    def row(view: SimulationView, who: PersonRef | None, why: list[str]) -> Candidate:
        affected = view.affected_responsibilities
        load = view.backup_load
        return Candidate(
            person=who,
            signals=why,
            covered=sum(1 for s in affected if s.cover != "uncovered"),
            total=len(affected),
            critical_gaps=sum(
                1
                for s in affected
                if s.cover == "uncovered" and s.criticality in ("critical", "high")
            ),
            knowledge_gaps=sum(
                1
                for s in affected
                if s.knowledge_total == 0 or s.knowledge_stale == s.knowledge_total
            ),
            remaining_risks=len(view.exposed_risks),
            readiness_score=view.readiness_score,
            load_after=load.current_responsibilities + load.would_take_over if load else None,
        )

    rows = []
    for pid in ranked:
        view = await simulate(access, person_id, pid, days)
        rows.append(row(view, view.backup, signals[pid]))
    rows.append(row(baseline, None, ["Nobody steps in"]))
    return CandidatesView(person=_ref(person), candidates=rows, basis=CANDIDATE_BASIS)
