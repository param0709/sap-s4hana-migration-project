"""Day 5 CVI and Business Partner readiness response models."""

import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.constants.enums import IssueSeverity


class BusinessPartnerCategoryRead(BaseModel):
    code: str
    label: str


class AccountGroupMappingRead(BaseModel):
    ecc_account_group: str
    bp_grouping: str
    record_count: int = Field(ge=0)


class UnmappedAccountGroupRead(BaseModel):
    ecc_account_group: str
    record_count: int = Field(ge=0)
    source_rows: list[int]


class CviCheckRead(BaseModel):
    check_id: str
    name: str
    status: Literal["passed", "failed"]
    severity: IssueSeverity
    affected_records: int = Field(ge=0)
    affected_source_rows: list[int]
    explanation: str
    suggested_action: str


class CviReadinessRead(BaseModel):
    project_id: uuid.UUID
    uploaded_file_id: uuid.UUID
    methodology_version: Literal["v1"]
    target_object: str
    disclaimer: str
    status: Literal["ready", "blocked"]
    cvi_ready: bool
    total_records: int = Field(ge=0)
    records_ready: int = Field(ge=0)
    records_blocked: int = Field(ge=0)
    failed_checks: int = Field(ge=0)
    critical_blockers: int = Field(ge=0)
    bp_category: BusinessPartnerCategoryRead
    required_bp_roles: list[str]
    mapped_account_groups: list[AccountGroupMappingRead]
    unmapped_account_groups: list[UnmappedAccountGroupRead]
    checks: list[CviCheckRead]
