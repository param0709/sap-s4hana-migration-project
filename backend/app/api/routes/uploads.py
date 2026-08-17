"""ECC Customer Master upload endpoints (FR-004 to FR-010)."""
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.constants.cvi import (
    ACCOUNT_GROUP_TO_BP_GROUPING,
    BP_CATEGORY_CODE,
    BP_CATEGORY_LABEL,
    CVI_DISCLAIMER,
    REQUIRED_BP_ROLES,
    TARGET_OBJECT,
)
from app.constants.ecc_schema import COLUMN_DESCRIPTIONS, OPTIONAL_COLUMNS, REQUIRED_COLUMNS
from app.database import get_db
from app.schemas.assessment import AssessmentSummaryRead, FileIssuesRead
from app.schemas.cvi import CviReadinessRead
from app.schemas.profile import FileProfileRead
from app.schemas.readiness import ReadinessRead
from app.schemas.upload import UploadedFileRead
from app.services import (
    assessment_service,
    cvi_service,
    file_service,
    profiling_service,
    project_service,
    readiness_service,
)
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


@router.post(
    "/{file_id}/assessment",
    response_model=AssessmentSummaryRead,
    status_code=status.HTTP_200_OK,
)
def run_assessment(
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> AssessmentSummaryRead:
    """Run deterministic BR-001–BR-014 assessment and persist record-level issues."""
    try:
        summary = assessment_service.assess_file(db, project_id, file_id)
    except assessment_service.AssessmentDataUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "ASSESSMENT_DATA_UNAVAILABLE", "message": str(exc)},
        ) from exc

    if summary is None:
        raise HTTPException(status_code=404, detail="Uploaded file not found in this project.")
    return AssessmentSummaryRead.model_validate(summary)


@router.get("/{file_id}/issues", response_model=FileIssuesRead)
def list_file_issues(
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> FileIssuesRead:
    """Return persisted issues for one file in stable source-row/rule order (FR-017, FR-018)."""
    result = assessment_service.get_file_issues(db, project_id, file_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Uploaded file not found in this project.")
    return FileIssuesRead.model_validate(result)


@router.get("/{file_id}/readiness", response_model=ReadinessRead)
def get_file_readiness(
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ReadinessRead:
    """Return the deterministic Migration Readiness Score (methodology v1).

    Read-only: it never mutates state and never runs assessment on its own. The
    file must have completed assessment first, otherwise a 409 asks the
    consultant to run assessment. This is a project-defined readiness indicator,
    not an official SAP metric.
    """
    try:
        result = readiness_service.calculate_readiness(db, project_id, file_id)
    except readiness_service.ReadinessDataUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "READINESS_DATA_UNAVAILABLE", "message": str(exc)},
        ) from exc
    except readiness_service.AssessmentRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "ASSESSMENT_REQUIRED", "message": str(exc)},
        ) from exc

    if result is None:
        raise HTTPException(status_code=404, detail="Uploaded file not found in this project.")
    return ReadinessRead.model_validate(result)


@router.get("/{file_id}/cvi-readiness", response_model=CviReadinessRead)
def get_cvi_readiness(
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> CviReadinessRead:
    """Return the Day 5 CVI and Business Partner readiness pre-check."""
    try:
        result = cvi_service.calculate_cvi_readiness(db, project_id, file_id)
    except cvi_service.CviDataUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CVI_DATA_UNAVAILABLE", "message": str(exc)},
        ) from exc
    except cvi_service.CviAssessmentRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "ASSESSMENT_REQUIRED", "message": str(exc)},
        ) from exc

    if result is None:
        raise HTTPException(status_code=404, detail="Uploaded file not found in this project.")
    return CviReadinessRead.model_validate(result)


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


@reference_router.get("/cvi")
def cvi_reference() -> dict:
    """Expose the synthetic Day 5 CVI configuration used by the pre-check."""
    return {
        "target_object": TARGET_OBJECT,
        "bp_category": {"code": BP_CATEGORY_CODE, "label": BP_CATEGORY_LABEL},
        "required_bp_roles": list(REQUIRED_BP_ROLES),
        "account_group_mappings": ACCOUNT_GROUP_TO_BP_GROUPING,
        "disclaimer": CVI_DISCLAIMER,
    }
