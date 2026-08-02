"""Database foundation tests for persisted migration issues."""
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.constants.enums import IssueSeverity, IssueStatus, IssueType
from app.models import MigrationIssue, MigrationRecord


def _upload_record(client, project, db_session) -> MigrationRecord:
    content = (
        b"KUNNR,NAME1,ORT01,LAND1,KTOKD,BUKRS,SMTP_ADDR\n"
        b"00001001,Alpha,Mumbai,IN,ZDOM,1000,bad-email\n"
    )
    response = client.post(
        f"{settings.api_prefix}/projects/{project['id']}/files/ecc",
        files={"file": ("issues.csv", content, "text/csv")},
    )
    assert response.status_code == 201
    return db_session.scalar(
        select(MigrationRecord).where(
            MigrationRecord.uploaded_file_id == uuid.UUID(response.json()["id"])
        )
    )


def _issue(record: MigrationRecord, rule_id: str = "BR-006") -> MigrationIssue:
    return MigrationIssue(
        project_id=record.project_id,
        uploaded_file_id=record.uploaded_file_id,
        migration_record_id=record.id,
        source_row_number=record.source_row_number,
        rule_id=rule_id,
        rule_name="Email format",
        field_name="SMTP_ADDR",
        severity=IssueSeverity.MEDIUM,
        current_value="bad-email",
        reason="Email address has an invalid format.",
        suggested_action="Enter a valid email address or leave the optional field blank.",
    )


def test_migration_issue_is_registered_on_base_metadata():
    assert MigrationIssue.__tablename__ in MigrationIssue.metadata.tables


def test_issue_persists_with_record_file_and_project_links(
    client, project, db_session
):
    record = _upload_record(client, project, db_session)
    issue = _issue(record)
    db_session.add(issue)
    db_session.commit()
    db_session.refresh(issue)

    assert issue.project_id == record.project_id
    assert issue.uploaded_file_id == record.uploaded_file_id
    assert issue.migration_record_id == record.id
    assert issue.source_row_number == 1
    assert issue.issue_type == IssueType.BUSINESS_RULE
    assert issue.issue_status == IssueStatus.OPEN
    assert issue.current_value == "bad-email"
    assert issue.created_at is not None


def test_record_and_rule_pair_is_unique(client, project, db_session):
    record = _upload_record(client, project, db_session)
    db_session.add(_issue(record))
    db_session.commit()
    db_session.add(_issue(record))

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_one_record_can_have_findings_from_different_rules(
    client, project, db_session
):
    record = _upload_record(client, project, db_session)
    db_session.add_all([_issue(record, "BR-006"), _issue(record, "BR-010")])
    db_session.commit()

    issues = db_session.scalars(
        select(MigrationIssue).where(MigrationIssue.migration_record_id == record.id)
    ).all()
    assert {issue.rule_id for issue in issues} == {"BR-006", "BR-010"}
