"""Persisted source rows used by later migration stages."""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.constants.enums import RecordStatus
from app.database import Base
from app.models.types import JSONType


class MigrationRecord(Base):
    """One addressable row from an accepted ECC source-data upload."""

    __tablename__ = "migration_records"
    __table_args__ = (
        UniqueConstraint(
            "uploaded_file_id",
            "source_row_number",
            name="uq_migration_records_file_row",
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
    source_row_number: Mapped[int] = mapped_column(Integer)

    # original_data is treated as immutable by application services. Later
    # transformations operate only on working_data.
    original_data: Mapped[dict[str, Any]] = mapped_column(JSONType)
    working_data: Mapped[dict[str, Any]] = mapped_column(JSONType)
    record_status: Mapped[str] = mapped_column(
        String(32),
        default=RecordStatus.PENDING,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
