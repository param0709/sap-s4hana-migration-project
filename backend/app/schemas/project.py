"""Request and response models for the project endpoints."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.constants.enums import ProjectStatus


class ProjectCreate(BaseModel):
    """Payload for creating a migration project (US-001).

    Text fields are stripped before length constraints are applied, so a value
    made up only of spaces is rejected rather than stored as blank.
    """

    project_name: str = Field(min_length=2, max_length=200)
    client_name: str = Field(min_length=2, max_length=200)
    source_system: str = Field(default="SAP ECC", min_length=1, max_length=100)
    target_system: str = Field(default="SAP S/4HANA", min_length=1, max_length=100)
    migration_object: str = Field(default="Customer Master", min_length=1, max_length=100)
    country: str = Field(default="IN", pattern=r"^[A-Z]{2}$")
    description: str | None = Field(default=None, max_length=1000)

    @field_validator(
        "project_name",
        "client_name",
        "source_system",
        "target_system",
        "migration_object",
        mode="before",
    )
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("country", mode="before")
    @classmethod
    def normalise_country(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("description", mode="before")
    @classmethod
    def blank_description_is_none(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_code: str
    project_name: str
    client_name: str
    source_system: str
    target_system: str
    migration_object: str
    country: str
    status: ProjectStatus
    description: str | None
    created_at: datetime
    updated_at: datetime


class ProjectList(BaseModel):
    total: int
    items: list[ProjectRead]
