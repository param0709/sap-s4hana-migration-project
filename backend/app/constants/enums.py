"""Enumerations shared across models and API schemas."""
from enum import StrEnum


class ProjectStatus(StrEnum):
    DRAFT = "draft"
    UPLOADED = "uploaded"
    ASSESSED = "assessed"
    UNDER_REVIEW = "under_review"
    EXPORT_READY = "export_ready"
    COMPLETED = "completed"
    FAILED = "failed"


class FileCategory(StrEnum):
    SOURCE_DATA = "source_data"
    TARGET_TEMPLATE = "target_template"
    MAPPING = "mapping"
    BUSINESS_RULES = "business_rules"
    MIGRATION_GUIDE = "migration_guide"


class ProcessingStatus(StrEnum):
    ACCEPTED = "accepted"
    SCHEMA_ERRORS = "schema_errors"
    REJECTED = "rejected"


class IssueSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RecordStatus(StrEnum):
    """Readiness status of one persisted source record."""

    PENDING = "pending"


class IssueType(StrEnum):
    """Source of a migration issue."""

    BUSINESS_RULE = "business_rule"


class IssueStatus(StrEnum):
    """Lifecycle status of a migration issue."""

    OPEN = "open"
