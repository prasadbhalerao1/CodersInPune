"""Platform tables: the tenant boundary and the isolation probe.

Tenant-scoped table conventions (enforced by tests/security/test_schema_conventions.py):
- `tenant_id uuid NOT NULL` referencing `platform.tenant(id)`.
- `UNIQUE (tenant_id, id)` so other tenant tables can reference it with a composite FK.
- Every other unique key starts with `tenant_id`.
- References to tenant-scoped rows are composite `(tenant_id, x_id)` foreign keys.
- RLS enabled and forced, with the `tenant_isolation` policy (see migrations).
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from relay.shared.db.base import Base

SCHEMA = "platform"
_UUIDV7 = text("uuidv7()")


class Tenant(Base):
    __tablename__ = "tenant"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Owner scheduled deletion; purged by `relay-purge-workspaces` after the grace period.
    deletion_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deletion_requested_by: Mapped[uuid.UUID | None]


class TenantProbe(Base):
    """Minimal tenant-scoped table that exists to prove isolation end to end."""

    __tablename__ = "tenant_probe"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "name"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TenantProbeItem(Base):
    """Child of `TenantProbe`; demonstrates the composite tenant foreign key."""

    __tablename__ = "tenant_probe_item"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "probe_id"],
            ["platform.tenant_probe.tenant_id", "platform.tenant_probe.id"],
        ),
        Index(None, "tenant_id", "probe_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    probe_id: Mapped[uuid.UUID]
    label: Mapped[str] = mapped_column(Text)


class RateLimitWindow(Base):
    """Fixed-window hit counts shared by every API replica (migration 0038).

    Global, not tenant data: the app role has no grants and only calls
    `platform.rate_limit_hit` (SECURITY DEFINER).
    """

    __tablename__ = "rate_limit_window"
    __table_args__ = {"schema": SCHEMA}

    bucket: Mapped[str] = mapped_column(Text, primary_key=True)
    subject: Mapped[str] = mapped_column(Text, primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    hits: Mapped[int]
