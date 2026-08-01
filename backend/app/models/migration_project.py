"""migration_projects table."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants.enums import ProjectStatus
from app.database import Base


class MigrationProject(Base):
    """A single ECC-to-S/4HANA migration engagement."""

    __tablename__ = "migration_projects"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)

    project_name: Mapped[str] = mapped_column(String(200))
    client_name: Mapped[str] = mapped_column(String(200))
    source_system: Mapped[str] = mapped_column(String(100), default="SAP ECC")
    target_system: Mapped[str] = mapped_column(String(100), default="SAP S/4HANA")
    migration_object: Mapped[str] = mapped_column(String(100), default="Customer Master")
    country: Mapped[str] = mapped_column(String(2), default="IN")

    status: Mapped[str] = mapped_column(String(32), default=ProjectStatus.DRAFT, index=True)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    files: Mapped[list["UploadedFile"]] = relationship(  # noqa: F821
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="UploadedFile.uploaded_at.desc()",
    )
