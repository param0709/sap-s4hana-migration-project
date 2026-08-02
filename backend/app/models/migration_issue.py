"""Persisted migration findings produced by assessment rules."""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.constants.enums import IssueStatus, IssueType
from app.database import Base
from app.models.types import JSONType


class MigrationIssue(Base):
    """One deterministic finding attached to one source record."""

    __tablename__ = "migration_issues"
    __table_args__ = (
        UniqueConstraint(
            "migration_record_id",
            "rule_id",
            name="uq_migration_issues_record_rule",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("migration_projects.id", ondelete="CASCADE"),
        index=True,
    )
    uploaded_file_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("uploaded_files.id", ondelete="CASCADE"),
        index=True,
    )
    migration_record_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("migration_records.id", ondelete="CASCADE"),
        index=True,
    )
    source_row_number: Mapped[int] = mapped_column(Integer)

    issue_type: Mapped[str] = mapped_column(
        String(32),
        default=IssueType.BUSINESS_RULE,
        index=True,
    )
    rule_id: Mapped[str] = mapped_column(String(32))
    rule_name: Mapped[str] = mapped_column(String(200))
    field_name: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16), index=True)
    current_value: Mapped[Any | None] = mapped_column(JSONType, nullable=True)
    reason: Mapped[str] = mapped_column(String(500))
    suggested_action: Mapped[str] = mapped_column(String(500))
    issue_status: Mapped[str] = mapped_column(
        String(32),
        default=IssueStatus.OPEN,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
