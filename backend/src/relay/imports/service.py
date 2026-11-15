"""CSV import for the catalogue: people, responsibilities and ownership assignments.

One flow for every kind: parse -> validate each row against the live workspace -> preview
-> commit. Commit re-validates (the workspace may have changed since the preview) and
writes every valid row in one transaction, each through the normal service functions, so
permissions, audit, ownership history and database constraints all apply unchanged.

Rows that match something that already exists are skipped, never updated, and an import
never replaces an existing owner: a different primary owner is reported as an error that
points to a transfer case.
"""

import csv
import io
import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints, ValidationError
from sqlalchemy import func, select

from relay.audit import service as audit
from relay.catalog import service as catalog
from relay.catalog.models import OwnershipAssignment, Responsibility
from relay.directory import service as directory
from relay.directory.models import Department, Person, Team
from relay.identity.workspace_access import WorkspaceAccess
from relay.policy.permissions import Permission, authorize, visible
from relay.shared.api_types import StrictInput
from relay.shared.errors import ApiError

Kind = Literal["people", "responsibilities", "assignments"]
Action = Literal["create", "skip", "error"]

MAX_ROWS = 1000
CsvText = Annotated[str, StringConstraints(min_length=1, max_length=512_000)]

COLUMNS: dict[Kind, tuple[tuple[str, ...], tuple[str, ...]]] = {
    # kind: (required, optional)
    "people": (("name",), ("email", "title", "github_login", "department")),
    "responsibilities": (("name",), ("description", "category", "criticality")),
    "assignments": (("responsibility", "owner", "role"), ("owner_type",)),
}
_ALIASES = {"display_name": "name", "person": "owner", "team": "owner", "github": "github_login"}
_PERMISSION: dict[Kind, Permission] = {
    "people": Permission.DIRECTORY_MANAGE,
    "responsibilities": Permission.RESPONSIBILITY_MANAGE,
    "assignments": Permission.RESPONSIBILITY_MANAGE,
}


class ImportIn(StrictInput):
    kind: Kind
    csv: CsvText


class ImportRowView(BaseModel):
    line: int
    action: Action
    label: str
    message: str | None = None


class ImportResultView(BaseModel):
    kind: Kind
    committed: bool
    columns: list[str]
    ignored_columns: list[str]
    rows: list[ImportRowView]
    created: int
    skipped: int
    errors: int


@dataclass
class _Row:
    line: int
    label: str
    action: Action = "create"
    message: str | None = None
    person: directory.PersonIn | None = None
    department: str | None = None
    responsibility: catalog.ResponsibilityIn | None = None
    assignment: tuple[uuid.UUID, catalog.AssignmentIn] | None = None


@dataclass
class _Lookup:
    """Live workspace state, loaded once per import (keys are case-folded)."""

    people_by_email: dict[str, Person] = field(default_factory=dict)
    people_by_name: dict[str, list[Person]] = field(default_factory=dict)
    teams_by_name: dict[str, list[Team]] = field(default_factory=dict)
    departments: dict[str, Department] = field(default_factory=dict)
    responsibilities: dict[str, list[Responsibility]] = field(default_factory=dict)


def _key(value: str) -> str:
    return " ".join(value.split()).casefold()


def _parse(kind: Kind, text: str) -> tuple[list[str], list[str], list[tuple[int, dict[str, str]]]]:
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    try:
        header = next(reader)
    except StopIteration:
        raise ApiError(422, "empty_csv", "The file is empty.") from None
    columns = [_ALIASES.get(h.strip().lower(), h.strip().lower()) for h in header]
    required, optional = COLUMNS[kind]
    missing = [c for c in required if c not in columns]
    if missing:
        raise ApiError(
            422, "missing_columns", f"The file needs these columns: {', '.join(missing)}."
        )
    known = set(required) | set(optional)
    rows: list[tuple[int, dict[str, str]]] = []
    for values in reader:
        if not any(v.strip() for v in values):
            continue
        if len(rows) >= MAX_ROWS:
            raise ApiError(422, "too_many_rows", f"Import at most {MAX_ROWS} rows at a time.")
        record = {
            c: v.strip() for c, v in zip(columns, values, strict=False) if c in known and v.strip()
        }
        rows.append((reader.line_num, record))
    return [c for c in columns if c in known], [c for c in columns if c not in known], rows


async def _lookup(access: WorkspaceAccess) -> _Lookup:
    lookup = _Lookup()
    for p in await access.session.scalars(
        select(Person).where(visible(access, Permission.DIRECTORY_READ, Person.tenant_id))
    ):
        if p.email:
            lookup.people_by_email[p.email.casefold()] = p
        lookup.people_by_name.setdefault(_key(p.display_name), []).append(p)
    for t in await access.session.scalars(
        select(Team).where(visible(access, Permission.DIRECTORY_READ, Team.tenant_id))
    ):
        lookup.teams_by_name.setdefault(_key(t.name), []).append(t)
    for d in await access.session.scalars(
        select(Department).where(visible(access, Permission.DIRECTORY_READ, Department.tenant_id))
    ):
        lookup.departments[_key(d.name)] = d
    for r in await access.session.scalars(
        select(Responsibility).where(
            visible(access, Permission.RESPONSIBILITY_READ, Responsibility.tenant_id)
        )
    ):
        lookup.responsibilities.setdefault(_key(r.name), []).append(r)
    return lookup


def _first_error(exc: ValidationError) -> str:
    error = exc.errors()[0]
    where = ".".join(str(p) for p in error["loc"]).replace("display_name", "name") or "value"
    if error["type"] == "string_pattern_mismatch":
        return f"{where} is not valid."
    if error["type"] == "literal_error":
        return f"{where} must be one of: {error['ctx']['expected']}."
    return f"{where}: {error['msg']}"


def _check_people(rows: list[tuple[int, dict[str, str]]], lookup: _Lookup) -> list[_Row]:
    checked: list[_Row] = []
    seen: Counter[str] = Counter()
    for line, r in rows:
        row = _Row(line, r.get("name", ""))
        identity = (r.get("email") or r.get("name", "")).casefold()
        seen[identity] += 1
        try:
            row.person = directory.PersonIn(
                display_name=r.get("name", ""),
                email=r.get("email"),
                title=r.get("title"),
                github_login=r.get("github_login"),
            )
        except ValidationError as exc:
            row.action, row.message = "error", _first_error(exc)
        else:
            by_name = lookup.people_by_name.get(_key(r["name"]), [])
            existing = (
                lookup.people_by_email.get(r["email"].casefold())
                if r.get("email")
                else (by_name[0] if by_name else None)
            )
            department = r.get("department")
            if seen[identity] > 1:
                row.action, row.message = "error", "Appears more than once in this file."
            elif existing is not None:
                row.action, row.message = "skip", "Already in the directory; left unchanged."
            elif department:
                found = lookup.departments.get(_key(department))
                if found is not None and found.status != "active":
                    row.action, row.message = "error", f"Department “{department}” is archived."
                else:
                    row.department = department
                    if found is None:
                        row.message = f"Creates the department “{department}”."
        checked.append(row)
    return checked


def _check_responsibilities(rows: list[tuple[int, dict[str, str]]], lookup: _Lookup) -> list[_Row]:
    checked: list[_Row] = []
    seen: Counter[str] = Counter()
    for line, r in rows:
        row = _Row(line, r.get("name", ""))
        seen[_key(r.get("name", ""))] += 1
        try:
            row.responsibility = catalog.ResponsibilityIn(
                name=r.get("name", ""),
                description=r.get("description"),
                category=r.get("category"),
                criticality=r.get("criticality", "standard").lower(),
            )
        except ValidationError as exc:
            row.action, row.message = "error", _first_error(exc)
        else:
            if seen[_key(r["name"])] > 1:
                row.action, row.message = "error", "Appears more than once in this file."
            elif _key(r["name"]) in lookup.responsibilities:
                row.action, row.message = "skip", "A responsibility with this name exists."
        checked.append(row)
    return checked


def _resolve_owner(
    owner: str, owner_type: str | None, lookup: _Lookup
) -> tuple[catalog.Assignee | None, str | None]:
    if owner_type not in (None, "person", "team"):
        return None, "owner_type must be person or team."
    if owner_type != "team":
        person = lookup.people_by_email.get(owner.casefold())
        people = [person] if person else lookup.people_by_name.get(_key(owner), [])
        if len(people) == 1:
            return catalog.Assignee(person_id=people[0].id), None
        if len(people) > 1:
            return None, f"More than one person is called “{owner}”; use their email."
    if owner_type != "person":
        teams = lookup.teams_by_name.get(_key(owner), [])
        if len(teams) == 1:
            return catalog.Assignee(team_id=teams[0].id), None
    return None, f"No person or team matches “{owner}”. Import people first."


async def _check_assignments(
    access: WorkspaceAccess, rows: list[tuple[int, dict[str, str]]], lookup: _Lookup
) -> list[_Row]:
    current = list(
        await access.session.scalars(
            select(OwnershipAssignment).where(
                visible(access, Permission.RESPONSIBILITY_READ, OwnershipAssignment.tenant_id),
                catalog.active_at(catalog.utcnow()),
            )
        )
    )
    names = await catalog.assignee_views(access.session, current)
    checked: list[_Row] = []
    planned_primary: dict[uuid.UUID, uuid.UUID] = {}
    for line, r in rows:
        row = _Row(line, f"{r.get('owner', '')} → {r.get('responsibility', '')}")
        checked.append(row)
        role = r.get("role", "").lower().replace("-", "_").replace(" ", "_")
        if role not in ("primary", "co_owner", "backup"):
            row.action, row.message = "error", "role must be primary, co_owner or backup."
            continue
        matches = lookup.responsibilities.get(_key(r.get("responsibility", "")), [])
        if len(matches) != 1:
            row.action = "error"
            row.message = (
                "No responsibility has this name. Import responsibilities first."
                if not matches
                else "More than one responsibility has this name."
            )
            continue
        responsibility = matches[0]
        if responsibility.status != "active":
            row.action, row.message = "error", "The responsibility is archived."
            continue
        assignee, problem = _resolve_owner(r.get("owner", ""), r.get("owner_type"), lookup)
        if assignee is None:
            row.action, row.message = "error", problem
            continue
        holder = assignee.person_id or assignee.team_id
        assert holder is not None
        mine = [a for a in current if a.responsibility_id == responsibility.id]
        held = next((a for a in mine if (a.person_id or a.team_id) == holder), None)
        primary = next((a for a in mine if a.role == "primary"), None)
        if held is not None and held.role == role:
            row.action, row.message = "skip", "Already assigned; left unchanged."
        elif held is not None:
            row.action = "error"
            row.message = f"Already holds the {held.role.replace('_', '-')} role here."
        elif role == "primary" and primary is not None:
            row.action = "error"
            row.message = (
                f"{names[primary.person_id or primary.team_id].name} is already the primary "  # type: ignore[index]
                "owner. Change it with a transfer case; imports never replace owners."
            )
        elif role == "primary" and planned_primary.get(responsibility.id, holder) != holder:
            row.action, row.message = "error", "Another row already sets the primary owner."
        else:
            if role == "primary":
                planned_primary[responsibility.id] = holder
            row.assignment = (
                responsibility.id,
                catalog.AssignmentIn(
                    person_id=assignee.person_id,
                    team_id=assignee.team_id,
                    role=role,
                    reason="Imported from CSV",
                ),
            )
    return checked


async def _check(access: WorkspaceAccess, data: ImportIn) -> tuple[ImportResultView, list[_Row]]:
    authorize(access, _PERMISSION[data.kind])
    columns, ignored, rows = _parse(data.kind, data.csv)
    lookup = await _lookup(access)
    if data.kind == "people":
        checked = _check_people(rows, lookup)
    elif data.kind == "responsibilities":
        checked = _check_responsibilities(rows, lookup)
    else:
        checked = await _check_assignments(access, rows, lookup)
    return _result(data.kind, False, columns, ignored, checked), checked


def _result(
    kind: Kind, committed: bool, columns: list[str], ignored: list[str], rows: list[_Row]
) -> ImportResultView:
    counts = Counter(r.action for r in rows)
    return ImportResultView(
        kind=kind,
        committed=committed,
        columns=columns,
        ignored_columns=ignored,
        rows=[
            ImportRowView(line=r.line, action=r.action, label=r.label, message=r.message)
            for r in rows
        ],
        created=counts["create"],
        skipped=counts["skip"],
        errors=counts["error"],
    )


async def preview_import(access: WorkspaceAccess, data: ImportIn) -> ImportResultView:
    result, _ = await _check(access, data)
    return result


async def _department_id(
    access: WorkspaceAccess, name: str, created: dict[str, uuid.UUID]
) -> uuid.UUID:
    key = _key(name)
    if key not in created:
        existing = await access.session.scalar(
            select(Department.id).where(
                func.lower(Department.name) == name.lower(),
                visible(access, Permission.DIRECTORY_READ, Department.tenant_id),
            )
        )
        created[key] = (
            existing
            or (await directory.create_department(access, directory.DepartmentIn(name=name))).id
        )
    return created[key]


async def commit_import(access: WorkspaceAccess, data: ImportIn) -> ImportResultView:
    """All valid rows in one transaction; a row the database still rejects becomes an
    error row (its savepoint rolls back) without undoing the others."""
    preview, rows = await _check(access, data)
    departments: dict[str, uuid.UUID] = {}
    for row in rows:
        if row.action != "create":
            continue
        try:
            async with access.session.begin_nested():
                if row.person is not None:
                    if row.department:
                        row.person.department_id = await _department_id(
                            access, row.department, departments
                        )
                    await directory.create_person(access, row.person)
                elif row.responsibility is not None:
                    await catalog.add_responsibility(access, row.responsibility)
                elif row.assignment is not None:
                    await catalog.add_assignment(access, *row.assignment)
                row.message = None
        except ApiError as exc:
            row.action, row.message = "error", exc.detail
    result = _result(data.kind, True, preview.columns, preview.ignored_columns, rows)
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="import.committed",
        actor_user_id=access.user_id,
        target_type="import",
        details={
            "kind": data.kind,
            "created": result.created,
            "skipped": result.skipped,
            "errors": result.errors,
        },
    )
    return result
