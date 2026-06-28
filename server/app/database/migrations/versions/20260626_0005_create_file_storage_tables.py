"""create file storage tables"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260626_0005"
down_revision = "20260626_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create files and file_versions tables."""
    op.create_table(
        "files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("file_type", sa.String(length=40), nullable=False, server_default="file"),
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("file_type IN ('file')", name="ck_files_file_type"),
    )
    op.create_table(
        "file_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("devices.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("content_checksum", sa.String(length=256), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("version_number", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("size_bytes >= 0", name="ck_file_versions_size_nonnegative"),
        sa.CheckConstraint("version_number >= 1", name="ck_file_versions_version_positive"),
    )
    op.create_foreign_key("fk_files_current_version_id", "files", "file_versions", ["current_version_id"], ["id"])
    op.create_index("uq_files_workspace_path", "files", ["workspace_id", "path"], unique=True)
    op.create_index("idx_files_workspace_id", "files", ["workspace_id"])
    op.create_index("idx_files_deleted_at", "files", ["deleted_at"])
    op.create_index("idx_file_versions_file_id", "file_versions", ["file_id"])
    op.create_index("idx_file_versions_workspace_id", "file_versions", ["workspace_id"])
    op.create_index("idx_file_versions_created_by_device_id", "file_versions", ["created_by_device_id"])
    op.create_index("uq_file_versions_file_version", "file_versions", ["file_id", "version_number"], unique=True)


def downgrade() -> None:
    """Drop files and file_versions tables."""
    op.drop_index("uq_file_versions_file_version", table_name="file_versions")
    op.drop_index("idx_file_versions_created_by_device_id", table_name="file_versions")
    op.drop_index("idx_file_versions_workspace_id", table_name="file_versions")
    op.drop_index("idx_file_versions_file_id", table_name="file_versions")
    op.drop_index("idx_files_deleted_at", table_name="files")
    op.drop_index("idx_files_workspace_id", table_name="files")
    op.drop_index("uq_files_workspace_path", table_name="files")
    op.drop_constraint("fk_files_current_version_id", "files", type_="foreignkey")
    op.drop_table("file_versions")
    op.drop_table("files")
