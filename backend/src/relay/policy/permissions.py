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
    KNOWLEDGE_WRITE = "knowledge.write"
    MEMBER_MANAGE = "member.manage"
    INTEGRATION_MANAGE = "integration.manage"


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
        Permission.KNOWLEDGE_WRITE,
        Permission.MEMBER_MANAGE,
        Permission.INTEGRATION_MANAGE,
    }
)

ROLE_PERMISSIONS: Final[dict[str, frozenset[Permission]]] = {
    "owner": _READ | _MANAGE | {Permission.AUDIT_READ},
    "admin": _READ | _MANAGE | {Permission.AUDIT_READ},
    "auditor": _READ | {Permission.AUDIT_READ},
    "member": _READ | {Permission.CASE_COMMENT, Permission.KNOWLEDGE_WRITE},
    "guest": _READ,
}


class PermissionDenied(ApiError):
    """403 that the API layer also records as an `authorization.denied` audit event."""

    def __init__(self, access: WorkspaceAccess, permission: str) -> None:
        super().__init__(403, "forbidden", "You do not have permission to do this.")
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
