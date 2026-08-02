"""Create migration_issues.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-03
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_TYPE = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "migration_issues",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("uploaded_file_id", sa.Uuid(), nullable=False),
        sa.Column("migration_record_id", sa.Uuid(), nullable=False),
        sa.Column("source_row_number", sa.Integer(), nullable=False),
        sa.Column("issue_type", sa.String(length=32), nullable=False),
        sa.Column("rule_id", sa.String(length=32), nullable=False),
        sa.Column("rule_name", sa.String(length=200), nullable=False),
        sa.Column("field_name", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("current_value", JSON_TYPE, nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("suggested_action", sa.String(length=500), nullable=False),
        sa.Column("issue_status", sa.String(length=32), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["migration_record_id"],
            ["migration_records.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "migration_record_id",
            "rule_id",
            name="uq_migration_issues_record_rule",
        ),
    )
    op.create_index(
        "ix_migration_issues_project_id",
        "migration_issues",
        ["project_id"],
    )
    op.create_index(
        "ix_migration_issues_uploaded_file_id",
        "migration_issues",
        ["uploaded_file_id"],
    )
    op.create_index(
        "ix_migration_issues_migration_record_id",
        "migration_issues",
        ["migration_record_id"],
    )
    op.create_index(
        "ix_migration_issues_issue_type",
        "migration_issues",
        ["issue_type"],
    )
    op.create_index(
        "ix_migration_issues_severity",
        "migration_issues",
        ["severity"],
    )
    op.create_index(
        "ix_migration_issues_issue_status",
        "migration_issues",
        ["issue_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_migration_issues_issue_status", table_name="migration_issues")
    op.drop_index("ix_migration_issues_severity", table_name="migration_issues")
    op.drop_index("ix_migration_issues_issue_type", table_name="migration_issues")
    op.drop_index(
        "ix_migration_issues_migration_record_id",
        table_name="migration_issues",
    )
    op.drop_index(
        "ix_migration_issues_uploaded_file_id",
        table_name="migration_issues",
    )
    op.drop_index("ix_migration_issues_project_id", table_name="migration_issues")
    op.drop_table("migration_issues")
