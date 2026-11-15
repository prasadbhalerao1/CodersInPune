"""Permission registry: deny by default.

`authorize()` guards commands and protected reads; `visible()` builds the SQL predicate for
lists. Both are called *inside* service functions, so calling a service directly cannot skip
them. Roles are Relay-owned membership roles; nothing here reads WorkOS roles.

Only permissions used by existing features exist. Add an entry when a feature needs one.
"""

import logging
import uuid
from enum import StrEnum
from typing import Final

from sqlalchemy import ColumnElement, false
from sqlalchemy.orm import InstrumentedAttribute

from relay.identity.tokens import VerifiedIdentity
from relay.identity.workspace_access import WorkspaceAccess
from relay.shared.errors import ApiError

logger = logging.getLogger(__name__)


class Permission(StrEnum):
    WORKSPACE_CREATE = "workspace.create"
    WORKSPACE_READ = "workspace.read"
    WORKSPACE_DELETE = "workspace.delete"
    AUDIT_READ = "audit.read"
    DIRECTORY_READ = "directory.read"
    DIRECTORY_MANAGE = "directory.manage"
    RESPONSIBILITY_READ = "responsibility.read"
    RESPONSIBILITY_MANAGE = "responsibility.manage"
    MEMBER_READ = "member.read"
    CASE_READ = "case.read"
    CASE_MANAGE = "case.manage"
    CASE_APPROVE = "case.approve"
    CASE_COMMENT = "case.comment"
    CONTINUITY_SIMULATE = "continuity.simulate"
    KNOWLEDGE_WRITE = "knowledge.write"
    KNOWLEDGE_VERIFY = "knowledge.verify"
    MEMBER_MANAGE = "member.manage"
    INTEGRATION_MANAGE = "integration.manage"
    INSIGHTS_READ = "insights.read"
    POLICY_MANAGE = "policy.manage"
    AUTOMATION_MANAGE = "automation.manage"
    AI_READ = "ai.read"
    AI_RUN = "ai.run"
    AI_REVIEW = "ai.review"
    AI_ADMIN = "ai.admin"


# Granted to any verified identity, independent of workspace membership.
PRINCIPAL_PERMISSIONS: Final = frozenset({Permission.WORKSPACE_CREATE})

_READ: Final = frozenset(
    {
        Permission.WORKSPACE_READ,
        Permission.DIRECTORY_READ,
        Permission.RESPONSIBILITY_READ,
        Permission.MEMBER_READ,
        Permission.CASE_READ,
    }
)
_MANAGE: Final = frozenset(
    {
        Permission.DIRECTORY_MANAGE,
        Permission.RESPONSIBILITY_MANAGE,
        Permission.CASE_MANAGE,
        Permission.CASE_APPROVE,
        Permission.CASE_COMMENT,
        Permission.CONTINUITY_SIMULATE,
        Permission.KNOWLEDGE_WRITE,
        Permission.KNOWLEDGE_VERIFY,
        Permission.MEMBER_MANAGE,
        Permission.INTEGRATION_MANAGE,
        Permission.POLICY_MANAGE,
        Permission.AUTOMATION_MANAGE,
        Permission.AI_RUN,
        Permission.AI_REVIEW,
        Permission.AI_ADMIN,
    }
)

ROLE_PERMISSIONS: Final[dict[str, frozenset[Permission]]] = {
    "owner": _READ
    | _MANAGE
    | {
        Permission.AUDIT_READ,
        Permission.INSIGHTS_READ,
        Permission.AI_READ,
        Permission.WORKSPACE_DELETE,
    },
    "admin": _READ
    | _MANAGE
    | {Permission.AUDIT_READ, Permission.INSIGHTS_READ, Permission.AI_READ},
    "auditor": _READ | {Permission.AUDIT_READ, Permission.INSIGHTS_READ, Permission.AI_READ},
    # Members read AI output limited to workspace-audience evidence (D2).
    "member": _READ | {Permission.CASE_COMMENT, Permission.KNOWLEDGE_WRITE, Permission.AI_READ},
    "guest": _READ,
    # Runs continuity work (cases, approvals, ownership changes) without workspace admin.
    "continuity_manager": _READ
    | {
        Permission.RESPONSIBILITY_MANAGE,
        Permission.CASE_MANAGE,
        Permission.CASE_APPROVE,
        Permission.CASE_COMMENT,
        Permission.CONTINUITY_SIMULATE,
        Permission.KNOWLEDGE_WRITE,
        Permission.INSIGHTS_READ,
        Permission.AI_READ,
        Permission.AI_RUN,
        Permission.AI_REVIEW,
    },
    # Keeps knowledge trustworthy: verifies and resolves disputes anywhere.
    "knowledge_steward": _READ
    | {
        Permission.CASE_COMMENT,
        Permission.KNOWLEDGE_WRITE,
        Permission.KNOWLEDGE_VERIFY,
        Permission.AI_READ,
    },
    # A member who also manages the responsibilities their scoped teams hold
    # (catalog.service.authorize_responsibility); nothing workspace-wide.
    "team_manager": _READ
    | {Permission.CASE_COMMENT, Permission.KNOWLEDGE_WRITE, Permission.AI_READ},
}
# Plain-language summary of each role, for the Roles & Permissions screen.
ROLE_DESCRIPTIONS: Final[dict[str, str]] = {
    "owner": "Everything, including billing-level decisions and removing admins.",
    "admin": "Everything except transferring ownership.",
    "continuity_manager": "Runs cases, approvals and ownership changes; no member or "
    "integration administration.",
    "knowledge_steward": "Verifies knowledge and resolves disputes across the workspace.",
    "team_manager": "A member who manages the responsibilities held by their teams.",
    "member": "Reads the workspace, comments, writes knowledge and completes their tasks.",
    "auditor": "Reads everything, including the audit log; changes nothing.",
    "guest": "Reads the workspace; changes nothing.",
}


class PermissionDenied(ApiError):
    """403 that the API layer also records as an `authorization.denied` audit event."""

    def __init__(self, access: WorkspaceAccess, permission: str) -> None:
        roles = [
            r.replace("_", " ") for r, perms in ROLE_PERMISSIONS.items() if permission in perms
        ]
        hint = (
            f" It needs one of these roles: {', '.join(roles)}. Ask a workspace owner or admin."
            if roles
            else ""
        )
        super().__init__(403, "forbidden", f"You do not have permission to do this.{hint}")
        self.tenant_id: uuid.UUID = access.tenant_id
        self.user_id: uuid.UUID = access.user_id
        self.role = access.role
        self.permission = permission
        self.workos_user_id = access.workos_user_id


def _known(permission: str) -> Permission | None:
    try:
        return Permission(permission)
    except ValueError:
        return None


def role_allows(role: str, permission: str) -> bool:
    known = _known(permission)
    return known is not None and known in ROLE_PERMISSIONS.get(role, frozenset())


def authorize(access: WorkspaceAccess, permission: str) -> None:
    if not role_allows(access.role, permission):
        logger.info("denied %s for role %s in %s", permission, access.role, access.tenant_id)
        raise PermissionDenied(access, permission)


def authorize_principal(identity: VerifiedIdentity, permission: str) -> None:
    known = _known(permission)
    if known is None or known not in PRINCIPAL_PERMISSIONS:
        raise ApiError(403, "forbidden", "You do not have permission to do this.")


def visible(
    access: WorkspaceAccess, permission: str, tenant_column: InstrumentedAttribute[uuid.UUID]
) -> ColumnElement[bool]:
    """Row predicate for lists: rows of the resolved workspace only, or nothing at all.

    Redundant with RLS on purpose (defence in depth): a list can never widen beyond the
    workspace the caller was authorized for, even if a query forgets a filter.
    """
    if not role_allows(access.role, permission):
        return false()
    return tenant_column == access.tenant_id
