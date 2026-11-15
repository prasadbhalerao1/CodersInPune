"""Who in Relay may see evidence from a linked source (FR-INT-010, migration 0037).

Relay cannot mirror each person's permissions in GitHub, Linear or Notion, so it never
assumes a member could see a source there. Each linked source carries an audience:
'managers' (people who manage responsibilities) or 'workspace'. Private GitHub
repositories, Linear projects and Notion pages start as 'managers'; only an admin widens
one, as an audited decision. Every read path filters with these predicates, and the AI
evidence pool labels items with the same audience so outputs inherit it (D2).
"""

from sqlalchemy import ColumnElement, select, true
from sqlalchemy.orm import QueryableAttribute

from relay.identity.workspace_access import WorkspaceAccess
from relay.integrations.linear.models import LinearIssue, LinearProject
from relay.policy.permissions import Permission, role_allows


def sees_restricted(access: WorkspaceAccess) -> bool:
    """Managers see every linked source; everyone else only workspace-audience ones."""
    return role_allows(access.role, Permission.RESPONSIBILITY_MANAGE)


def shared(
    access: WorkspaceAccess, audience: QueryableAttribute[str] | QueryableAttribute[str | None]
) -> ColumnElement[bool]:
    """Row filter on a source's `audience` column."""
    return true() if sees_restricted(access) else audience == "workspace"


def linear_issue_shared(access: WorkspaceAccess) -> ColumnElement[bool]:
    """Linear issues are visible to non-managers only through a workspace-audience project."""
    if sees_restricted(access):
        return true()
    projects = select(LinearProject.linear_id).where(
        LinearProject.audience == "workspace", LinearProject.removed.is_(False)
    )
    return LinearIssue.project_linear_id.in_(projects)
