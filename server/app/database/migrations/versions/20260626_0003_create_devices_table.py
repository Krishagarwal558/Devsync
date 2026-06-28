"""create devices table"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260626_0003"
down_revision = "20260626_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create devices table."""
    op.create_table(
        "devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("platform", sa.String(length=80), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=True),
        sa.Column("trust_status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("trust_status IN ('pending', 'trusted', 'revoked')", name="ck_devices_trust_status"),
    )
    op.create_index("idx_devices_user_id", "devices", ["user_id"])
    op.create_index("idx_devices_trust_status", "devices", ["trust_status"])
    op.create_index("idx_devices_last_seen_at", "devices", ["last_seen_at"])
    op.create_index("idx_devices_deleted_at", "devices", ["deleted_at"])


def downgrade() -> None:
    """Drop devices table."""
    op.drop_index("idx_devices_deleted_at", table_name="devices")
    op.drop_index("idx_devices_last_seen_at", table_name="devices")
    op.drop_index("idx_devices_trust_status", table_name="devices")
    op.drop_index("idx_devices_user_id", table_name="devices")
    op.drop_table("devices")

