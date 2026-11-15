"""Unified identity review: where GitHub, Linear and the directory disagree about who
someone is. Read-only: each conflict links to where it is resolved (the person, or the
integration's identity matching), and nothing is merged automatically."""

import uuid
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import func, select

from relay.directory.models import Person
from relay.identity.workspace_access import WorkspaceAccess
from relay.integrations.github.models import GitHubIdentity
from relay.integrations.linear.models import LinearIdentity
from relay.policy.permissions import Permission, authorize, visible


class IdentityConflict(BaseModel):
    kind: Literal["github_login_mismatch", "email_mismatch", "duplicate_email", "pending_match"]
    provider: Literal["GitHub", "Linear", "Directory"]
    person_id: uuid.UUID | None
    person_name: str | None
    handle: str
    detail: str


async def identity_conflicts(access: WorkspaceAccess) -> list[IdentityConflict]:
    authorize(access, Permission.INTEGRATION_MANAGE)
    people = {
        p.id: p
        for p in await access.session.scalars(
            select(Person).where(visible(access, Permission.DIRECTORY_READ, Person.tenant_id))
        )
    }
    found: list[IdentityConflict] = []
    for g in await access.session.scalars(select(GitHubIdentity)):
        person = people.get(g.person_id) if g.person_id else None
        if person and person.github_login and person.github_login != g.login.lower():
            found.append(
                IdentityConflict(
                    kind="github_login_mismatch",
                    provider="GitHub",
                    person_id=person.id,
                    person_name=person.display_name,
                    handle=g.login,
                    detail=f"Linked to GitHub @{g.login}, but the directory says "
                    f"@{person.github_login}.",
                )
            )
        elif g.link_status == "suggested":
            found.append(
                IdentityConflict(
                    kind="pending_match",
                    provider="GitHub",
                    person_id=None,
                    person_name=None,
                    handle=g.login,
                    detail="A suggested match is waiting for a decision.",
                )
            )
    for li in await access.session.scalars(select(LinearIdentity)):
        person = people.get(li.person_id) if li.person_id else None
        if person and li.email and person.email and li.email.lower() != person.email.lower():
            found.append(
                IdentityConflict(
                    kind="email_mismatch",
                    provider="Linear",
                    person_id=person.id,
                    person_name=person.display_name,
                    handle=li.name,
                    detail=f"Linked to Linear user {li.email}, but the directory email is "
                    f"{person.email}.",
                )
            )
        elif li.link_status == "suggested":
            suggested = people.get(li.suggested_person_id) if li.suggested_person_id else None
            found.append(
                IdentityConflict(
                    kind="pending_match",
                    provider="Linear",
                    person_id=suggested.id if suggested else None,
                    person_name=suggested.display_name if suggested else None,
                    handle=li.name,
                    detail=li.match_reason or "A suggested match is waiting for a decision.",
                )
            )
    duplicates = await access.session.execute(
        select(func.lower(Person.email), func.count())
        .where(
            visible(access, Permission.DIRECTORY_READ, Person.tenant_id),
            Person.email.is_not(None),
            Person.status == "active",
        )
        .group_by(func.lower(Person.email))
        .having(func.count() > 1)
    )
    for email, count in duplicates:
        found.append(
            IdentityConflict(
                kind="duplicate_email",
                provider="Directory",
                person_id=None,
                person_name=None,
                handle=email,
                detail=f"{count} active people share this email; Relay can't tell them apart.",
            )
        )
    return found
