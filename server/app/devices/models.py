"""Device SQLAlchemy model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from server.app.auth.models import User
from server.app.database.base import Base, TimestampMixin


class Device(Base, TimestampMixin):
    """A computer or laptop registered by a user."""

    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    platform: Mapped[str] = mapped_column(String(80), nullable=False)
    public_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    trust_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(lazy="joined")


Index("idx_devices_user_id", Device.user_id)
Index("idx_devices_trust_status", Device.trust_status)
Index("idx_devices_last_seen_at", Device.last_seen_at)
Index("idx_devices_deleted_at", Device.deleted_at)

