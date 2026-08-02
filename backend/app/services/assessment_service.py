"""Apply deterministic business rules and persist their findings atomically."""
import uuid
from collections import Counter
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.constants.enums import (
    IssueSeverity,
    IssueStatus,
    IssueType,
    ProjectStatus,
    RecordStatus,
)
from app.models import MigrationIssue, MigrationProject, MigrationRecord, UploadedFile
from app.validation.business_rules import RuleFinding, evaluate_business_rules


class AssessmentDataUnavailableError(Exception):
    """An uploaded file does not have a complete persisted record set."""


def _issue_mapping(
    record: MigrationRecord,
    finding: RuleFinding,
) -> dict[str, Any]:
    return {
        "id": uuid.uuid4(),
        "project_id": record.project_id,
        "uploaded_file_id": record.uploaded_file_id,
        "migration_record_id": record.id,
        "source_row_number": record.source_row_number,
        "issue_type": IssueType.BUSINESS_RULE,
        "rule_id": finding.rule_id,
        "rule_name": finding.rule_name,
        "field_name": finding.field_name,
        "severity": finding.severity,
        "current_value": finding.current_value,
        "reason": finding.reason,
        "suggested_action": finding.suggested_action,
        "issue_status": IssueStatus.OPEN,
    }


def _summary(
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    findings_by_record: list[list[RuleFinding]],
) -> dict[str, Any]:
    findings = [finding for group in findings_by_record for finding in group]
    severity_counts = Counter(str(finding.severity) for finding in findings)
    rule_counts = Counter(finding.rule_id for finding in findings)
    records_needing_review = sum(bool(group) for group in findings_by_record)

    return {
        "project_id": project_id,
        "uploaded_file_id": file_id,
        "total_records": len(findings_by_record),
        "records_ready": len(findings_by_record) - records_needing_review,
        "records_needing_review": records_needing_review,
        "total_issues": len(findings),
        "issues_by_severity": {
            severity.value: severity_counts[severity.value]
            for severity in IssueSeverity
        },
        "issues_by_rule": dict(sorted(rule_counts.items())),
    }


def assess_file(
    db: Session,
    project_id: uuid.UUID,
    file_id: uuid.UUID,
) -> dict[str, Any] | None:
    """Assess one uploaded file and replace its deterministic findings.

    Evaluation reads only working_data. Existing business-rule issues for this
    file are replaced in the same transaction, making safe reruns non-additive.
    Findings from later duplicate or mapping modules are left untouched.
    """
    uploaded_file = db.scalar(
        select(UploadedFile).where(
            UploadedFile.id == file_id,
            UploadedFile.project_id == project_id,
        )
    )
    if uploaded_file is None:
        return None

    records = list(
        db.scalars(
            select(MigrationRecord)
            .where(
                MigrationRecord.project_id == project_id,
                MigrationRecord.uploaded_file_id == file_id,
            )
            .order_by(MigrationRecord.source_row_number)
        ).all()
    )
    if uploaded_file.row_count is not None and len(records) != uploaded_file.row_count:
        raise AssessmentDataUnavailableError(
            "The persisted record count does not match this upload's metadata. "
            "Re-upload the file before running assessment."
        )

    try:
        findings_by_record = evaluate_business_rules(
            [record.working_data or {} for record in records]
        )
        db.execute(
            delete(MigrationIssue).where(
                MigrationIssue.project_id == project_id,
                MigrationIssue.uploaded_file_id == file_id,
                MigrationIssue.issue_type == IssueType.BUSINESS_RULE,
            )
        )

        mappings: list[dict[str, Any]] = []
        for record, findings in zip(records, findings_by_record, strict=True):
            record.record_status = (
                RecordStatus.NEEDS_REVIEW if findings else RecordStatus.READY
            )
            mappings.extend(_issue_mapping(record, finding) for finding in findings)
        if mappings:
            db.execute(MigrationIssue.__table__.insert(), mappings)

        project = db.get(MigrationProject, project_id)
        if project is not None and project.status in {
            ProjectStatus.UPLOADED,
            ProjectStatus.ASSESSED,
        }:
            project.status = ProjectStatus.ASSESSED

        result = _summary(project_id, file_id, findings_by_record)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
