"""ECC Customer Master upload endpoints (FR-004 to FR-010)."""
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.constants.ecc_schema import COLUMN_DESCRIPTIONS, OPTIONAL_COLUMNS, REQUIRED_COLUMNS
from app.database import get_db
from app.schemas.profile import FileProfileRead
from app.schemas.upload import UploadedFileRead
from app.services import file_service, profiling_service, project_service
from app.validation.errors import FileRejectedError
from app.validation.file_rules import ALLOWED_EXTENSIONS

router = APIRouter(prefix="/projects/{project_id}/files", tags=["uploads"])


@router.post("/ecc", response_model=UploadedFileRead, status_code=status.HTTP_201_CREATED)
async def upload_ecc_file(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> UploadedFileRead:
    """Upload an ECC Customer Master extract and validate it against the schema."""
    if project_service.get_project(db, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found.")

    content = await file.read()

    try:
        record = file_service.ingest_ecc_file(db, project_id, file.filename, content)
    except FileRejectedError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.to_dict()
        ) from exc

    return UploadedFileRead.model_validate(record)


@router.get("", response_model=list[UploadedFileRead])
def list_files(project_id: uuid.UUID, db: Session = Depends(get_db)) -> list[UploadedFileRead]:
    if project_service.get_project(db, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    records = file_service.list_project_files(db, project_id)
    return [UploadedFileRead.model_validate(record) for record in records]


@router.get("/{file_id}/profile", response_model=FileProfileRead)
def get_file_profile(
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> FileProfileRead:
    """Return deterministic FR-011–FR-014 metrics for one source file."""
    try:
        profile = profiling_service.profile_file(db, project_id, file_id)
    except profiling_service.ProfileDataUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "PROFILE_DATA_UNAVAILABLE", "message": str(exc)},
        ) from exc

    if profile is None:
        raise HTTPException(status_code=404, detail="Uploaded file not found in this project.")
    return FileProfileRead.model_validate(profile)


reference_router = APIRouter(prefix="/reference", tags=["reference"])


@reference_router.get("/ecc-schema")
def ecc_schema() -> dict:
    """Expose the expected ECC layout so the upload screen can show it."""
    return {
        "allowed_extensions": sorted(ALLOWED_EXTENSIONS),
        "required_columns": [
            {"name": name, "description": COLUMN_DESCRIPTIONS[name]} for name in REQUIRED_COLUMNS
        ],
        "optional_columns": [
            {"name": name, "description": COLUMN_DESCRIPTIONS[name]} for name in OPTIONAL_COLUMNS
        ],
    }
