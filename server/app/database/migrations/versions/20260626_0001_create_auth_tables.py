"""create auth tables"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260626_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create users and sessions tables."""
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('active', 'disabled', 'deleted')", name="ck_users_status"),
    )
    op.create_index("uq_users_email", "users", ["email"], unique=True)
    op.create_index("idx_users_status", "users", ["status"])
    op.create_index("idx_users_deleted_at", "users", ["deleted_at"])

    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("uq_sessions_refresh_token_hash", "sessions", ["refresh_token_hash"], unique=True)
    op.create_index("idx_sessions_user_id", "sessions", ["user_id"])
    op.create_index("idx_sessions_expires_at", "sessions", ["expires_at"])
    op.create_index("idx_sessions_revoked_at", "sessions", ["revoked_at"])


def downgrade() -> None:
    """Drop users and sessions tables."""
    op.drop_index("idx_sessions_revoked_at", table_name="sessions")
    op.drop_index("idx_sessions_expires_at", table_name="sessions")
    op.drop_index("idx_sessions_user_id", table_name="sessions")
    op.drop_index("uq_sessions_refresh_token_hash", table_name="sessions")
    op.drop_table("sessions")

    op.drop_index("idx_users_deleted_at", table_name="users")
    op.drop_index("idx_users_status", table_name="users")
    op.drop_index("uq_users_email", table_name="users")
    op.drop_table("users")

