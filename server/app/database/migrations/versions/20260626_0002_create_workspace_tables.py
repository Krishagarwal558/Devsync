"""create workspace tables"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260626_0002"
down_revision = "20260626_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create workspaces and workspace_members tables."""
    op.create_table(
        "workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("settings", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('active', 'archived', 'deleted')", name="ck_workspaces_status"),
    )
    op.create_index("idx_workspaces_owner_id", "workspaces", ["owner_id"])
    op.create_index("idx_workspaces_status", "workspaces", ["status"])
    op.create_index("idx_workspaces_deleted_at", "workspaces", ["deleted_at"])
    op.create_index(
        "uq_workspaces_owner_slug_active",
        "workspaces",
        ["owner_id", "slug"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND status <> 'deleted'"),
    )

    op.create_table(
        "workspace_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('owner', 'admin', 'developer', 'viewer')", name="ck_workspace_members_role"),
        sa.CheckConstraint("status IN ('active', 'removed')", name="ck_workspace_members_status"),
    )
    op.create_index("idx_workspace_members_workspace_id", "workspace_members", ["workspace_id"])
    op.create_index("idx_workspace_members_user_id", "workspace_members", ["user_id"])
    op.create_index("idx_workspace_members_role", "workspace_members", ["role"])
    op.create_index("idx_workspace_members_status", "workspace_members", ["status"])
    op.create_index(
        "uq_workspace_members_workspace_user_active",
        "workspace_members",
        ["workspace_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND status = 'active'"),
    )


def downgrade() -> None:
    """Drop workspace tables."""
    op.drop_index("uq_workspace_members_workspace_user_active", table_name="workspace_members")
    op.drop_index("idx_workspace_members_status", table_name="workspace_members")
    op.drop_index("idx_workspace_members_role", table_name="workspace_members")
    op.drop_index("idx_workspace_members_user_id", table_name="workspace_members")
    op.drop_index("idx_workspace_members_workspace_id", table_name="workspace_members")
    op.drop_table("workspace_members")

    op.drop_index("uq_workspaces_owner_slug_active", table_name="workspaces")
    op.drop_index("idx_workspaces_deleted_at", table_name="workspaces")
    op.drop_index("idx_workspaces_status", table_name="workspaces")
    op.drop_index("idx_workspaces_owner_id", table_name="workspaces")
    op.drop_table("workspaces")

