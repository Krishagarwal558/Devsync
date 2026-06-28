"""Synchronization event SQLAlchemy model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from server.app.database.base import Base, utc_now
from server.app.devices.models import Device
from server.app.workspaces.models import Workspace


class SyncEvent(Base):
    """Ordered synchronization metadata event for a workspace."""

    __tablename__ = "sync_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    sender_device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    checksum: Mapped[str | None] = mapped_column(String(256), nullable=True)
    bandwidth_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="accepted")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    workspace: Mapped[Workspace] = relationship(lazy="joined")
    sender_device: Mapped[Device] = relationship(lazy="joined")


Index("uq_sync_events_workspace_sequence", SyncEvent.workspace_id, SyncEvent.sequence, unique=True)
Index("idx_sync_events_workspace_created_at", SyncEvent.workspace_id, SyncEvent.created_at)
Index("idx_sync_events_workspace_sender", SyncEvent.workspace_id, SyncEvent.sender_device_id)
Index("idx_sync_events_workspace_event_type", SyncEvent.workspace_id, SyncEvent.event_type)
Index("idx_sync_events_workspace_status", SyncEvent.workspace_id, SyncEvent.status)

