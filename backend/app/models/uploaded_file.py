"""uploaded_files table."""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.types import JSONType


class UploadedFile(Base):
    """Metadata for one file uploaded into a migration project.

    The stored original is never modified; `storage_path` always points at the
    untouched bytes exactly as received.
    """

    __tablename__ = "uploaded_files"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("migration_projects.id", ondelete="CASCADE"), index=True
    )

    file_name: Mapped[str] = mapped_column(String(255))
    file_category: Mapped[str] = mapped_column(String(32), index=True)
    file_extension: Mapped[str] = mapped_column(String(10))
    file_size_bytes: Mapped[int] = mapped_column(Integer)
    storage_path: Mapped[str] = mapped_column(String(500))

    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detected_columns: Mapped[list[str] | None] = mapped_column(JSONType, nullable=True)
    schema_errors: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONType, nullable=True)

    processing_status: Mapped[str] = mapped_column(String(32), index=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    project: Mapped["MigrationProject"] = relationship(back_populates="files")  # noqa: F821
