"""Integration tests for deterministic assessment persistence."""
import copy
import uuid

import pytest
from sqlalchemy import func, select

from app.config import settings
from app.constants.enums import FileCategory, ProcessingStatus, RecordStatus
from app.models import MigrationIssue, MigrationRecord, UploadedFile
from app.services import assessment_service


def _upload(client, project, content: bytes, name: str = "assessment.csv") -> dict:
    response = client.post(
        f"{settings.api_prefix}/projects/{project['id']}/files/ecc",
        files={"file": (name, content, "text/csv")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _records(db_session, file_id: str) -> list[MigrationRecord]:
    return list(
        db_session.scalars(
            select(MigrationRecord)
            .where(MigrationRecord.uploaded_file_id == uuid.UUID(file_id))
            .order_by(MigrationRecord.source_row_number)
        ).all()
    )


def _issues(db_session, file_id: str) -> list[MigrationIssue]:
    return list(
        db_session.scalars(
            select(MigrationIssue)
            .where(MigrationIssue.uploaded_file_id == uuid.UUID(file_id))
            .order_by(MigrationIssue.source_row_number, MigrationIssue.rule_id)
        ).all()
    )


def _two_record_content() -> bytes:
    return (
        b"KUNNR,NAME1,ORT01,LAND1,KTOKD,BUKRS,STCD3,SMTP_ADDR,LOEVM\n"
        b"00001001,Alpha,Mumbai,IN,ZDOM,1000,27ABCDE1234F1Z5,a@example.com,\n"
        b"00001002,Beta,Pune,IN,ZDOM,1000,,bad-email,X\n"
    )


def test_assessment_persists_issues_and_updates_record_statuses(
    client, project, db_session
):
    uploaded = _upload(client, project, _two_record_content())

    result = assessment_service.assess_file(
        db_session,
        uuid.UUID(project["id"]),
        uuid.UUID(uploaded["id"]),
    )
    records = _records(db_session, uploaded["id"])
    issues = _issues(db_session, uploaded["id"])

    assert result["total_records"] == 2
    assert result["records_ready"] == 1
    assert result["records_needing_review"] == 1
    assert result["total_issues"] == 3
    assert [record.record_status for record in records] == [
        RecordStatus.READY,
        RecordStatus.NEEDS_REVIEW,
    ]
    assert [issue.rule_id for issue in issues] == ["BR-004", "BR-006", "BR-010"]


def test_assessment_summary_counts_severity_and_rules(client, project, db_session):
    uploaded = _upload(client, project, _two_record_content())

    result = assessment_service.assess_file(
        db_session,
        uuid.UUID(project["id"]),
        uuid.UUID(uploaded["id"]),
    )

    assert result["issues_by_severity"] == {
        "critical": 1,
        "high": 1,
        "medium": 1,
        "low": 0,
    }
    assert result["issues_by_rule"] == {"BR-004": 1, "BR-006": 1, "BR-010": 1}


def test_persisted_issue_contains_complete_rule_and_record_context(
    client, project, db_session
):
    uploaded = _upload(client, project, _two_record_content())
    assessment_service.assess_file(
        db_session,
        uuid.UUID(project["id"]),
        uuid.UUID(uploaded["id"]),
    )

    issue = next(
        item for item in _issues(db_session, uploaded["id"]) if item.rule_id == "BR-006"
    )
    assert issue.project_id == uuid.UUID(project["id"])
    assert issue.migration_record_id == _records(db_session, uploaded["id"])[1].id
    assert issue.source_row_number == 3
    assert issue.field_name == "SMTP_ADDR"
    assert issue.current_value == "bad-email"
    assert issue.reason
    assert issue.suggested_action
    assert issue.issue_status == "open"


def test_assessment_marks_project_assessed(client, project, db_session):
    uploaded = _upload(client, project, _two_record_content())

    assessment_service.assess_file(
        db_session,
        uuid.UUID(project["id"]),
        uuid.UUID(uploaded["id"]),
    )

    refreshed = client.get(f"{settings.api_prefix}/projects/{project['id']}").json()
    assert refreshed["status"] == "assessed"


def test_rerun_replaces_findings_without_accumulating_duplicates(
    client, project, db_session
):
    uploaded = _upload(client, project, _two_record_content())
    project_id = uuid.UUID(project["id"])
    file_id = uuid.UUID(uploaded["id"])

    first = assessment_service.assess_file(db_session, project_id, file_id)
    second = assessment_service.assess_file(db_session, project_id, file_id)

    assert first == second
    assert len(_issues(db_session, uploaded["id"])) == 3


def test_rerun_removes_resolved_findings(client, project, db_session):
    uploaded = _upload(client, project, _two_record_content())
    project_id = uuid.UUID(project["id"])
    file_id = uuid.UUID(uploaded["id"])
    assessment_service.assess_file(db_session, project_id, file_id)
    record = _records(db_session, uploaded["id"])[1]
    original_before = copy.deepcopy(record.original_data)
    record.working_data = {
        **record.working_data,
        "STCD3": "27ABCDE1234F1Z5",
        "SMTP_ADDR": "b@example.com",
        "LOEVM": None,
    }
    db_session.commit()

    result = assessment_service.assess_file(db_session, project_id, file_id)

    assert result["total_issues"] == 0
    assert len(_issues(db_session, uploaded["id"])) == 0
    assert _records(db_session, uploaded["id"])[1].record_status == RecordStatus.READY
    assert _records(db_session, uploaded["id"])[1].original_data == original_before


def test_assessment_reads_working_data_and_preserves_original_data(
    client, project, db_session
):
    content = (
        b"KUNNR,NAME1,ORT01,LAND1,KTOKD,BUKRS,STCD3,SMTP_ADDR\n"
        b"1,Alpha,Mumbai,IN,ZDOM,1000,27ABCDE1234F1Z5,a@example.com\n"
    )
    uploaded = _upload(client, project, content)
    record = _records(db_session, uploaded["id"])[0]
    original_before = copy.deepcopy(record.original_data)
    record.working_data = {**record.working_data, "SMTP_ADDR": "bad-email"}
    db_session.commit()

    assessment_service.assess_file(
        db_session,
        uuid.UUID(project["id"]),
        uuid.UUID(uploaded["id"]),
    )

    assert [issue.rule_id for issue in _issues(db_session, uploaded["id"])] == [
        "BR-006"
    ]
    assert _records(db_session, uploaded["id"])[0].original_data == original_before


def test_duplicate_rule_is_persisted_for_every_affected_record(
    client, project, db_session
):
    content = (
        b"KUNNR,NAME1,ORT01,LAND1,KTOKD,BUKRS,STCD3\n"
        b"1,Alpha,Mumbai,IN,ZDOM,1000,27ABCDE1234F1Z5\n"
        b"1,Beta,Pune,IN,ZDOM,1000,27ABCDE1234F1Z5\n"
    )
    uploaded = _upload(client, project, content)

    assessment_service.assess_file(
        db_session,
        uuid.UUID(project["id"]),
        uuid.UUID(uploaded["id"]),
    )

    duplicate_issues = [
        issue
        for issue in _issues(db_session, uploaded["id"])
        if issue.rule_id == "BR-008"
    ]
    assert [issue.source_row_number for issue in duplicate_issues] == [2, 3]


def test_unknown_or_cross_project_file_returns_none(client, project, db_session):
    uploaded = _upload(client, project, _two_record_content())
    other = client.post(
        f"{settings.api_prefix}/projects",
        json={"project_name": "Other Project", "client_name": "Other Client"},
    ).json()

    assert assessment_service.assess_file(
        db_session,
        uuid.UUID(other["id"]),
        uuid.UUID(uploaded["id"]),
    ) is None
    assert assessment_service.assess_file(
        db_session,
        uuid.UUID(project["id"]),
        uuid.uuid4(),
    ) is None


def test_incomplete_persisted_records_raise_actionable_error(
    client, project, db_session
):
    file_id = uuid.uuid4()
    project_id = uuid.UUID(project["id"])
    db_session.add(
        UploadedFile(
            id=file_id,
            project_id=project_id,
            file_name="legacy.csv",
            file_category=FileCategory.SOURCE_DATA,
            file_extension=".csv",
            file_size_bytes=100,
            storage_path="storage/legacy.csv",
            row_count=1,
            column_count=2,
            detected_columns=["KUNNR", "NAME1"],
            schema_errors=[],
            processing_status=ProcessingStatus.ACCEPTED,
        )
    )
    db_session.commit()

    with pytest.raises(
        assessment_service.AssessmentDataUnavailableError,
        match="Re-upload",
    ):
        assessment_service.assess_file(db_session, project_id, file_id)

    issue_count = db_session.scalar(select(func.count()).select_from(MigrationIssue))
    assert issue_count == 0


def test_evaluation_failure_rolls_back_without_removing_existing_issues(
    client, project, db_session, monkeypatch
):
    uploaded = _upload(client, project, _two_record_content())
    project_id = uuid.UUID(project["id"])
    file_id = uuid.UUID(uploaded["id"])
    assessment_service.assess_file(db_session, project_id, file_id)
    before = [
        (issue.source_row_number, issue.rule_id)
        for issue in _issues(db_session, uploaded["id"])
    ]

    def fail_evaluation(_):
        raise RuntimeError("rule evaluation failed")

    monkeypatch.setattr(
        assessment_service,
        "evaluate_business_rules",
        fail_evaluation,
    )

    with pytest.raises(RuntimeError, match="rule evaluation failed"):
        assessment_service.assess_file(db_session, project_id, file_id)

    after = [
        (issue.source_row_number, issue.rule_id)
        for issue in _issues(db_session, uploaded["id"])
    ]
    assert after == before
