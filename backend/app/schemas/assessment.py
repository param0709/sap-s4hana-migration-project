"""Response models for the deterministic business-rule assessment API (FR-015–FR-018)."""
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.constants.enums import IssueSeverity


class SeverityCounts(BaseModel):
    """Issue totals for each documented severity band."""

    critical: int = Field(ge=0)
    high: int = Field(ge=0)
    medium: int = Field(ge=0)
    low: int = Field(ge=0)


class AssessmentSummaryRead(BaseModel):
    """Readiness and issue roll-up returned when an assessment runs."""

    project_id: uuid.UUID
    uploaded_file_id: uuid.UUID
    total_records: int = Field(ge=0)
    records_ready: int = Field(ge=0)
    records_needing_review: int = Field(ge=0)
    total_issues: int = Field(ge=0)
    issues_by_severity: SeverityCounts
    issues_by_rule: dict[str, int]

    @field_validator("issues_by_rule")
    @classmethod
    def _rule_counts_are_non_negative(cls, value: dict[str, int]) -> dict[str, int]:
        if any(count < 0 for count in value.values()):
            raise ValueError("Issue counts grouped by rule ID must be non-negative.")
        return value


class MigrationIssueRead(BaseModel):
    """One persisted finding with the full review context of FR-017 and FR-018."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    uploaded_file_id: uuid.UUID
    migration_record_id: uuid.UUID
    source_row_number: int
    issue_type: str
    rule_id: str
    rule_name: str
    field_name: str
    severity: IssueSeverity
    current_value: Any | None
    reason: str
    suggested_action: str
    issue_status: str
    created_at: datetime


class FileIssuesRead(BaseModel):
    """Every persisted issue for one uploaded file, in stable review order."""

    project_id: uuid.UUID
    uploaded_file_id: uuid.UUID
    total_issues: int = Field(ge=0)
    items: list[MigrationIssueRead]
