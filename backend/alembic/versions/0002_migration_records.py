"""Create migration_records.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-02
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_TYPE = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "migration_records",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("uploaded_file_id", sa.Uuid(), nullable=False),
        sa.Column("source_row_number", sa.Integer(), nullable=False),
        sa.Column("original_data", JSON_TYPE, nullable=False),
        sa.Column("working_data", JSON_TYPE, nullable=False),
        sa.Column("record_status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["migration_projects.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_file_id"],
            ["uploaded_files.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "uploaded_file_id",
            "source_row_number",
            name="uq_migration_records_file_row",
        ),
    )
    op.create_index(
        "ix_migration_records_project_id",
        "migration_records",
        ["project_id"],
    )
    op.create_index(
        "ix_migration_records_uploaded_file_id",
        "migration_records",
        ["uploaded_file_id"],
    )
    op.create_index(
        "ix_migration_records_record_status",
        "migration_records",
        ["record_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_migration_records_record_status", table_name="migration_records")
    op.drop_index(
        "ix_migration_records_uploaded_file_id",
        table_name="migration_records",
    )
    op.drop_index("ix_migration_records_project_id", table_name="migration_records")
    op.drop_table("migration_records")
