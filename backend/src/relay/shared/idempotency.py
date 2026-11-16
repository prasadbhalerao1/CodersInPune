"""Idempotent creates: a retried or double-submitted request returns the first result.

The client sends one `Idempotency-Key` per submission intent. `claim` records it in the same
transaction as the resource, so a failed request leaves no trace and may be retried; a
repeat after success gets the original resource id back; reusing a key for a different
request is rejected. Requests without a key behave as before.
"""

import hashlib
import json
import uuid
from typing import Annotated, Any

from fastapi import Header
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from relay.identity.workspace_access import WorkspaceAccess
from relay.platform.models import RequestKey
from relay.shared.errors import ApiError

OptionalIdempotencyKey = Annotated[
    str | None,
    Header(alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"),
]


def _hash(scope: str, payload: Any) -> str:
    body = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(f"{scope}\n{body}".encode()).hexdigest()


async def claim(
    access: WorkspaceAccess, key: str | None, scope: str, payload: Any
) -> uuid.UUID | None:
    """The resource a previous identical request created, or None to go ahead and create.

    Concurrent duplicates wait on the unique key, then see the first one's committed result.
    """
    if key is None:
        return None
    digest = _hash(scope, payload)
    await access.session.execute(
        insert(RequestKey)
        .values(tenant_id=access.tenant_id, key=key, scope=scope, request_hash=digest)
        .on_conflict_do_nothing(index_elements=["tenant_id", "key"])
    )
    row = await access.session.scalar(
        select(RequestKey).where(RequestKey.tenant_id == access.tenant_id, RequestKey.key == key)
    )
    if row is None or row.resource_id is None:
        return None  # ours: freshly inserted in this transaction
    if row.scope != scope or row.request_hash != digest:
        raise ApiError(
            422,
            "idempotency_key_reused",
            "This request key was already used for a different request. Submit the form again.",
        )
    return row.resource_id


async def remember(access: WorkspaceAccess, key: str | None, resource_id: uuid.UUID) -> None:
    """Record what this request created (same transaction as the resource)."""
    if key is None:
        return
    row = await access.session.scalar(
        select(RequestKey).where(RequestKey.tenant_id == access.tenant_id, RequestKey.key == key)
    )
    if row is not None and row.resource_id is None:
        row.resource_id = resource_id
