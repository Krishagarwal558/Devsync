"""Workspace SQLAlchemy models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from server.app.auth.models import User
from server.app.database.base import Base, TimestampMixin


class Workspace(Base, TimestampMixin):
    """A synchronized workspace owned by a user."""

    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(180), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    settings: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner: Mapped[User] = relationship(lazy="joined")
    members: Mapped[list["WorkspaceMember"]] = relationship(
        back_populates="workspace",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class WorkspaceMember(Base, TimestampMixin):
    """A user's membership in a workspace."""

    __tablename__ = "workspace_members"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workspace: Mapped[Workspace] = relationship(back_populates="members", lazy="joined")
    user: Mapped[User] = relationship(lazy="joined")


Index("idx_workspaces_owner_id", Workspace.owner_id)
Index("idx_workspaces_status", Workspace.status)
Index("idx_workspaces_deleted_at", Workspace.deleted_at)
Index(
    "uq_workspaces_owner_slug_active",
    Workspace.owner_id,
    Workspace.slug,
    unique=True,
    postgresql_where=(Workspace.deleted_at.is_(None) & (Workspace.status != "deleted")),
)
Index("idx_workspace_members_workspace_id", WorkspaceMember.workspace_id)
Index("idx_workspace_members_user_id", WorkspaceMember.user_id)
Index("idx_workspace_members_role", WorkspaceMember.role)
Index("idx_workspace_members_status", WorkspaceMember.status)
Index(
    "uq_workspace_members_workspace_user_active",
    WorkspaceMember.workspace_id,
    WorkspaceMember.user_id,
    unique=True,
    postgresql_where=(WorkspaceMember.deleted_at.is_(None) & (WorkspaceMember.status == "active")),
)

