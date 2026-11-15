"""The 30/60/90-day continuation plan for whoever takes over a case's work.

Built by rules from the case itself, so every step names the record it comes from: the
scope items and who receives them, the open tasks, the unmet readiness checks and which
responsibilities have no written knowledge. The plan proposes; adding a step to the case's
tasks is the person's choice.
"""

import uuid
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import func, select

from relay.catalog.knowledge import readable as knowledge_readable
from relay.catalog.models import KnowledgeItem
from relay.continuity import service as cases
from relay.identity.workspace_access import WorkspaceAccess

Phase = Literal[30, 60, 90]
PHASES: dict[int, tuple[str, str]] = {
    30: ("First 30 days", "Shadow and stabilise: learn the critical work while help is near."),
    60: ("Days 31 to 60", "Take the lead, with the previous owner or a backup on hand."),
    90: ("Days 61 to 90", "Own it: close the gaps so the work no longer depends on one person."),
}
HIGH = ("critical", "high")


class PlanStep(BaseModel):
    phase: Phase
    title: str
    why: str
    source_kind: Literal["scope", "task", "criterion", "case"]
    source_label: str
    responsibility_id: uuid.UUID | None = None
    due_at: datetime
    already_task: bool


class PhaseView(BaseModel):
    days: Phase
    title: str
    goal: str
    steps: list[PlanStep]


class ContinuationPlan(BaseModel):
    case_id: uuid.UUID
    starts_at: datetime
    phases: list[PhaseView]


async def continuation_plan(access: WorkspaceAccess, case_id: uuid.UUID) -> ContinuationPlan:
    case = await cases.get_case(access, case_id)  # authorizes and hides restricted scope
    scope = [s for s in case.scope if not s.hidden and s.state != "excepted"]
    documented = {
        rid
        for rid, n in await access.session.execute(
            select(KnowledgeItem.responsibility_id, func.count())
            .where(
                KnowledgeItem.responsibility_id.in_([s.responsibility_id for s in scope]),
                KnowledgeItem.status == "active",
                knowledge_readable(access),
            )
            .group_by(KnowledgeItem.responsibility_id)
        )
        if n
    }
    titles = {t.title.strip().lower() for t in case.tasks}
    start = case.starts_at
    steps: list[PlanStep] = []

    def add(
        phase: Phase,
        title: str,
        why: str,
        kind: Literal["scope", "task", "criterion", "case"],
        label: str,
        rid: uuid.UUID | None = None,
    ) -> None:
        steps.append(
            PlanStep(
                phase=phase,
                title=title[:200],
                why=why,
                source_kind=kind,
                source_label=label,
                responsibility_id=rid,
                due_at=start + timedelta(days=phase),
                already_task=title.strip().lower() in titles,
            )
        )

    owner = case.affected_person_name or "the previous owner"
    for s in sorted(scope, key=lambda s: (s.criticality not in HIGH, s.responsibility_name)):
        r, who = s.responsibility_name, s.recipient.name if s.recipient else None
        if who is None:
            add(
                30, f"Name who takes over {r}", "No recipient yet.", "scope", r, s.responsibility_id
            )
            continue
        if s.criticality in HIGH:
            add(
                30,
                f"{who} shadows {owner} on {r}",
                f"{s.criticality.capitalize()} work: learn it while {owner} is still reachable.",
                "scope",
                r,
                s.responsibility_id,
            )
        add(
            60,
            f"{who} leads {r}",
            "Run it end to end, with a backup on hand for the first cycle.",
            "scope",
            r,
            s.responsibility_id,
        )
        if s.responsibility_id not in documented:
            add(
                60,
                f"Document how {r} works",
                "Nothing is written down for it yet.",
                "scope",
                r,
                s.responsibility_id,
            )
        if s.criticality in HIGH:
            add(
                90,
                f"Name and train a backup for {r}",
                "So it never depends on one person again.",
                "scope",
                r,
                s.responsibility_id,
            )
        add(
            90,
            f"Review the knowledge for {r}",
            "Re-verify what was handed over now that it has been used.",
            "scope",
            r,
            s.responsibility_id,
        )
    for c in case.criteria:
        if c.mandatory and c.status not in ("met", "waived"):
            add(
                30,
                f"Meet readiness check: {c.title}",
                "Required before the case can close.",
                "criterion",
                c.title,
            )
    for t in case.tasks:
        if t.status in ("done", "cancelled"):
            continue
        due = t.due_at
        phase: Phase = (
            30
            if due is None or due <= start + timedelta(days=30)
            else (60 if due <= start + timedelta(days=60) else 90)
        )
        steps.append(
            PlanStep(
                phase=phase,
                title=t.title,
                why=f"Open task{f', assigned to {t.assignee_name}' if t.assignee_name else ''}.",
                source_kind="task",
                source_label=t.title,
                due_at=due or start + timedelta(days=phase),
                already_task=True,
            )
        )
    add(
        90,
        "Close the case and record what was learned",
        "Ends the handover formally.",
        "case",
        case.title,
    )
    return ContinuationPlan(
        case_id=case.id,
        starts_at=start,
        phases=[
            PhaseView(
                days=days,
                title=PHASES[days][0],
                goal=PHASES[days][1],
                steps=[s for s in steps if s.phase == days],
            )
            for days in (30, 60, 90)
        ],
    )
