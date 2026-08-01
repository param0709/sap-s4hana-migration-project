"""Business logic for migration projects. Kept out of the API routes."""
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants.enums import ProjectStatus
from app.models import MigrationProject
from app.schemas.project import ProjectCreate


def generate_project_code(db: Session) -> str:
    """Produce a readable, unique project code such as MIG-2026-0007 (FR-002)."""
    year = datetime.now(timezone.utc).year
    prefix = f"MIG-{year}-"
    used = db.scalars(
        select(MigrationProject.project_code).where(
            MigrationProject.project_code.like(f"{prefix}%")
        )
    ).all()

    highest = 0
    for code in used:
        suffix = code.removeprefix(prefix)
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return f"{prefix}{highest + 1:04d}"


def create_project(db: Session, payload: ProjectCreate) -> MigrationProject:
    """Create a project in Draft status (US-001)."""
    project = MigrationProject(
        project_code=generate_project_code(db),
        project_name=payload.project_name,
        client_name=payload.client_name,
        source_system=payload.source_system,
        target_system=payload.target_system,
        migration_object=payload.migration_object,
        country=payload.country,
        description=payload.description,
        status=ProjectStatus.DRAFT,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def list_projects(db: Session, limit: int = 50, offset: int = 0) -> tuple[int, list[MigrationProject]]:
    """Return newest-first projects with a total count (FR-003)."""
    total = db.scalar(select(func.count()).select_from(MigrationProject)) or 0
    items = db.scalars(
        select(MigrationProject)
        .order_by(MigrationProject.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return total, list(items)


def get_project(db: Session, project_id) -> MigrationProject | None:
    return db.get(MigrationProject, project_id)


def mark_uploaded(db: Session, project: MigrationProject) -> MigrationProject:
    """Move a Draft project to Uploaded once readable source data is stored.

    A file with schema findings still counts: it is readable and stored. Any
    status beyond Draft is left untouched so this never walks the project
    backwards.
    """
    if project.status == ProjectStatus.DRAFT:
        project.status = ProjectStatus.UPLOADED
        db.add(project)
    return project
