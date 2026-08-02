"""Upload handling: validate, store the untouched original, record metadata.

The original bytes are written to disk exactly as received and never rewritten,
which satisfies FR-007 (original uploaded files remain unchanged).
"""
import copy
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.constants.enums import FileCategory, ProcessingStatus, RecordStatus
from app.models import MigrationProject, MigrationRecord, UploadedFile
from app.services import project_service
from app.services.storage import store_original
from app.validation.file_rules import validate_upload
from app.validation.parser import ParsedFile, read_tabular_file
from app.validation.schema_validator import validate_ecc_schema


def ingest_ecc_file(
    db: Session,
    project_id: uuid.UUID,
    file_name: str | None,
    content: bytes,
) -> UploadedFile:
    """Validate and register one ECC Customer Master upload.

    Raises FileRejectedError when the file cannot be accepted at all. Schema
    mismatches do not raise: the file is stored and the findings are attached.
    """
    clean_name, extension = validate_upload(content, file_name, settings.max_upload_bytes)
    parsed = read_tabular_file(content, clean_name, extension)
    detected_columns, schema_errors = validate_ecc_schema(parsed.headers)

    file_id = uuid.uuid4()
    storage_path = store_original(project_id, file_id, clean_name, content)

    status = ProcessingStatus.SCHEMA_ERRORS if schema_errors else ProcessingStatus.ACCEPTED

    record = UploadedFile(
        id=file_id,
        project_id=project_id,
        file_name=clean_name,
        file_category=FileCategory.SOURCE_DATA,
        file_extension=extension,
        file_size_bytes=len(content),
        storage_path=storage_path,
        row_count=parsed.row_count,
        column_count=parsed.column_count,
        detected_columns=detected_columns,
        schema_errors=[error.to_dict() for error in schema_errors],
        processing_status=status,
    )
    try:
        db.add(record)

        project = db.get(MigrationProject, project_id)
        if project is not None:
            project_service.mark_uploaded(db, project)

        # The record bulk insert below is a Core statement. Flush explicitly so
        # PostgreSQL can resolve both foreign keys without relying on implicit
        # ORM autoflush behaviour.
        db.flush()
        _persist_records(db, project_id, file_id, parsed)
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(record)
    return record


def _persist_records(
    db: Session,
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    parsed: ParsedFile,
) -> None:
    """Bulk-insert the parsed rows inside the caller's open transaction."""
    if not parsed.rows:
        return

    mappings = [
        {
            "id": uuid.uuid4(),
            "project_id": project_id,
            "uploaded_file_id": file_id,
            "source_row_number": index,
            "original_data": copy.deepcopy(row),
            "working_data": copy.deepcopy(row),
            "record_status": RecordStatus.PENDING,
        }
        for index, row in enumerate(parsed.rows, start=1)
    ]
    db.execute(MigrationRecord.__table__.insert(), mappings)


def list_project_files(db: Session, project_id: uuid.UUID) -> list[UploadedFile]:
    return list(
        db.scalars(
            select(UploadedFile)
            .where(UploadedFile.project_id == project_id)
            .order_by(UploadedFile.uploaded_at.desc())
        ).all()
    )
