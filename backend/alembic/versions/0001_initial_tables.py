"""Create migration_projects and uploaded_files.

Revision ID: 0001
Revises:
Create Date: 2026-08-01
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_TYPE = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "migration_projects",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("project_code", sa.String(length=32), nullable=False),
        sa.Column("project_name", sa.String(length=200), nullable=False),
        sa.Column("client_name", sa.String(length=200), nullable=False),
        sa.Column("source_system", sa.String(length=100), nullable=False),
        sa.Column("target_system", sa.String(length=100), nullable=False),
        sa.Column("migration_object", sa.String(length=100), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_migration_projects_project_code", "migration_projects", ["project_code"], unique=True)
    op.create_index("ix_migration_projects_status", "migration_projects", ["status"])

    op.create_table(
        "uploaded_files",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_category", sa.String(length=32), nullable=False),
        sa.Column("file_extension", sa.String(length=10), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("column_count", sa.Integer(), nullable=True),
        sa.Column("detected_columns", JSON_TYPE, nullable=True),
        sa.Column("schema_errors", JSON_TYPE, nullable=True),
        sa.Column("processing_status", sa.String(length=32), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["migration_projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_uploaded_files_project_id", "uploaded_files", ["project_id"])
    op.create_index("ix_uploaded_files_file_category", "uploaded_files", ["file_category"])
    op.create_index("ix_uploaded_files_processing_status", "uploaded_files", ["processing_status"])


def downgrade() -> None:
    op.drop_table("uploaded_files")
    op.drop_table("migration_projects")
