"""Request and response models for the upload endpoints."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.constants.enums import FileCategory, IssueSeverity, ProcessingStatus


class SchemaErrorRead(BaseModel):
    code: str
    severity: IssueSeverity
    message: str
    columns: list[str]


class UploadedFileRead(BaseModel):
    """Everything the upload screen needs (FR-006)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    file_name: str
    file_category: FileCategory
    file_extension: str
    file_size_bytes: int
    row_count: int | None
    column_count: int | None
    detected_columns: list[str] | None
    schema_errors: list[SchemaErrorRead] | None
    processing_status: ProcessingStatus
    uploaded_at: datetime


class UploadRejected(BaseModel):
    """Returned with HTTP 422 when a file fails the hard gate (FR-005)."""

    code: str
    message: str
    detail: dict = {}
