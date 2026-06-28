"""create sync events table"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260626_0004"
down_revision = "20260626_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create sync_events table."""
    op.create_table(
        "sync_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("devices.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("checksum", sa.String(length=256), nullable=True),
        sa.Column("bandwidth_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="accepted"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "event_type IN ('file_created', 'file_modified', 'file_deleted', 'folder_created', 'folder_deleted', 'rename', 'move', 'metadata_changed')",
            name="ck_sync_events_event_type",
        ),
        sa.CheckConstraint("status IN ('accepted', 'acknowledged')", name="ck_sync_events_status"),
        sa.CheckConstraint("sequence >= 1", name="ck_sync_events_sequence_positive"),
        sa.CheckConstraint("bandwidth_bytes >= 0", name="ck_sync_events_bandwidth_nonnegative"),
    )
    op.create_index("uq_sync_events_workspace_sequence", "sync_events", ["workspace_id", "sequence"], unique=True)
    op.create_index("idx_sync_events_workspace_created_at", "sync_events", ["workspace_id", "created_at"])
    op.create_index("idx_sync_events_workspace_sender", "sync_events", ["workspace_id", "sender_device_id"])
    op.create_index("idx_sync_events_workspace_event_type", "sync_events", ["workspace_id", "event_type"])
    op.create_index("idx_sync_events_workspace_status", "sync_events", ["workspace_id", "status"])


def downgrade() -> None:
    """Drop sync_events table."""
    op.drop_index("idx_sync_events_workspace_status", table_name="sync_events")
    op.drop_index("idx_sync_events_workspace_event_type", table_name="sync_events")
    op.drop_index("idx_sync_events_workspace_sender", table_name="sync_events")
    op.drop_index("idx_sync_events_workspace_created_at", table_name="sync_events")
    op.drop_index("uq_sync_events_workspace_sequence", table_name="sync_events")
    op.drop_table("sync_events")
