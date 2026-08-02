"""Response models for the deterministic Migration Readiness Score (methodology v1).

The score is a project-defined, transparent, deterministic readiness indicator —
not an official SAP metric. See ``app.services.readiness_service`` for the single
source of truth that produces these values.
"""
import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.constants.enums import ReadinessBand


class ReadinessComponentRead(BaseModel):
    """One weighted component of the overall readiness score."""

    score: float = Field(ge=0, le=100)
    weight: float = Field(ge=0, le=1)
    weighted_score: float = Field(ge=0, le=100)


class ReadinessComponentsRead(BaseModel):
    """The four deterministic components that make up methodology v1."""

    schema_conformity: ReadinessComponentRead
    data_completeness: ReadinessComponentRead
    record_readiness: ReadinessComponentRead
    issue_severity: ReadinessComponentRead


class ReadinessRead(BaseModel):
    """Structured readiness result for one assessed uploaded file."""

    project_id: uuid.UUID
    uploaded_file_id: uuid.UUID
    methodology_version: Literal["v1"]
    score: float = Field(ge=0, le=100)
    band: ReadinessBand
    migration_ready: bool
    critical_blockers: int = Field(ge=0)
    total_records: int = Field(ge=0)
    records_ready: int = Field(ge=0)
    records_needing_review: int = Field(ge=0)
    total_issues: int = Field(ge=0)
    components: ReadinessComponentsRead
