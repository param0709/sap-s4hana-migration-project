"""Response models for deterministic source-data profiling."""
import uuid

from pydantic import BaseModel, Field


class FieldProfileRead(BaseModel):
    field_name: str
    total_records: int = Field(ge=0)
    missing_values: int = Field(ge=0)
    non_missing_values: int = Field(ge=0)
    unique_values: int = Field(ge=0)
    completeness_percentage: float = Field(ge=0, le=100)


class DuplicateGroupRead(BaseModel):
    representative_row_number: int = Field(ge=1)
    duplicate_row_numbers: list[int]
    record_count: int = Field(ge=2)
    duplicate_count: int = Field(ge=1)


class FileProfileRead(BaseModel):
    project_id: uuid.UUID
    uploaded_file_id: uuid.UUID
    file_name: str
    total_records: int = Field(ge=0)
    total_fields: int = Field(ge=0)
    total_missing_values: int = Field(ge=0)
    overall_completeness_percentage: float = Field(ge=0, le=100)
    exact_duplicate_records: int = Field(ge=0)
    exact_duplicate_groups: int = Field(ge=0)
    fields: list[FieldProfileRead]
    duplicate_groups: list[DuplicateGroupRead]
