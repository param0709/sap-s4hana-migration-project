"""Migration project endpoints (FR-001, FR-002, FR-003)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.project import ProjectCreate, ProjectList, ProjectRead
from app.services import project_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> ProjectRead:
    """Create a migration project. The new project starts in Draft status."""
    project = project_service.create_project(db, payload)
    return ProjectRead.model_validate(project)


@router.get("", response_model=ProjectList)
def list_projects(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> ProjectList:
    """List projects, newest first, so earlier work can be resumed."""
    total, items = project_service.list_projects(db, limit=limit, offset=offset)
    return ProjectList(total=total, items=[ProjectRead.model_validate(i) for i in items])


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: uuid.UUID, db: Session = Depends(get_db)) -> ProjectRead:
    project = project_service.get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return ProjectRead.model_validate(project)
