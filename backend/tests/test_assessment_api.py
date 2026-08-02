"""API integration tests for the deterministic assessment endpoints.

These exercise the real HTTP surface (FR-015–FR-018) through the SQLite test
client. The runtime PostgreSQL database is unaffected; only the schema-compatible
JSON columns and portable SQLAlchemy queries are used here.
"""
import uuid

import pytest
from sqlalchemy import func, select

from app.config import settings
from app.constants.enums import FileCategory, ProcessingStatus
from app.models import MigrationIssue, UploadedFile

PREFIX = settings.api_prefix


def _upload(client, project, content: bytes, name: str = "assessment.csv") -> dict:
    response = client.post(
        f"{PREFIX}/projects/{project['id']}/files/ecc",
        files={"file": (name, content, "text/csv")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _assessment_url(project_id: str, file_id: str) -> str:
    return f"{PREFIX}/projects/{project_id}/files/{file_id}/assessment"


def _issues_url(project_id: str, file_id: str) -> str:
    return f"{PREFIX}/projects/{project_id}/files/{file_id}/issues"


def _mixed_content() -> bytes:
    """Row 1 is clean; row 2 raises BR-004 (critical), BR-006 (medium), BR-010 (high)."""
    return (
        b"KUNNR,NAME1,ORT01,LAND1,KTOKD,BUKRS,STCD3,SMTP_ADDR,LOEVM\n"
        b"00001001,Alpha,Mumbai,IN,ZDOM,1000,27ABCDE1234F1Z5,a@example.com,\n"
        b"00001002,Beta,Pune,IN,ZDOM,1000,,bad-email,X\n"
    )


def _ordering_content() -> bytes:
    """Row 1 raises only BR-010, row 2 raises only BR-001.

    The rule IDs are deliberately reversed against row order so that a stable
    ordering must sort by source row before rule ID.
    """
    return (
        b"KUNNR,NAME1,ORT01,LAND1,KTOKD,BUKRS,STCD3,SMTP_ADDR,LOEVM\n"
        b"00001001,Alpha,Mumbai,IN,ZDOM,1000,27ABCDE1234F1Z5,a@example.com,X\n"
        b",Beta,Pune,IN,ZDOM,1000,27ABCDE1234F1Z5,b@example.com,\n"
    )


def test_post_assessment_returns_readiness_counts(client, project):
    uploaded = _upload(client, project, _mixed_content())

    response = client.post(_assessment_url(project["id"], uploaded["id"]))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["project_id"] == project["id"]
    assert body["uploaded_file_id"] == uploaded["id"]
    assert body["total_records"] == 2
    assert body["records_ready"] == 1
    assert body["records_needing_review"] == 1
    assert body["total_issues"] == 3


def test_severity_counts_contain_all_four_bands(client, project):
    uploaded = _upload(client, project, _mixed_content())

    body = client.post(_assessment_url(project["id"], uploaded["id"])).json()

    assert body["issues_by_severity"] == {
        "critical": 1,
        "high": 1,
        "medium": 1,
        "low": 0,
    }


def test_issue_counts_grouped_by_rule_id(client, project):
    uploaded = _upload(client, project, _mixed_content())

    body = client.post(_assessment_url(project["id"], uploaded["id"])).json()

    assert body["issues_by_rule"] == {"BR-004": 1, "BR-006": 1, "BR-010": 1}


def test_get_issues_returns_complete_persisted_details(client, project):
    uploaded = _upload(client, project, _mixed_content())
    client.post(_assessment_url(project["id"], uploaded["id"]))

    response = client.get(_issues_url(project["id"], uploaded["id"]))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["project_id"] == project["id"]
    assert body["uploaded_file_id"] == uploaded["id"]
    assert body["total_issues"] == 3

    email_issue = next(item for item in body["items"] if item["rule_id"] == "BR-006")
    assert set(email_issue) == {
        "id",
        "project_id",
        "uploaded_file_id",
        "migration_record_id",
        "source_row_number",
        "issue_type",
        "rule_id",
        "rule_name",
        "field_name",
        "severity",
        "current_value",
        "reason",
        "suggested_action",
        "issue_status",
        "created_at",
    }
    assert email_issue["project_id"] == project["id"]
    assert email_issue["uploaded_file_id"] == uploaded["id"]
    assert email_issue["source_row_number"] == 2
    assert email_issue["issue_type"] == "business_rule"
    assert email_issue["rule_name"] == "Email format"
    assert email_issue["field_name"] == "SMTP_ADDR"
    assert email_issue["severity"] == "medium"
    assert email_issue["current_value"] == "bad-email"
    assert email_issue["reason"]
    assert email_issue["suggested_action"]
    assert email_issue["issue_status"] == "open"
    assert uuid.UUID(email_issue["id"])
    assert email_issue["created_at"]


def test_issues_ordered_by_source_row_then_rule_id(client, project):
    uploaded = _upload(client, project, _ordering_content())
    client.post(_assessment_url(project["id"], uploaded["id"]))

    body = client.get(_issues_url(project["id"], uploaded["id"])).json()

    assert [item["source_row_number"] for item in body["items"]] == [1, 2]
    assert [item["rule_id"] for item in body["items"]] == ["BR-010", "BR-001"]


def test_get_issues_before_assessment_returns_empty_collection(client, project):
    uploaded = _upload(client, project, _mixed_content())

    response = client.get(_issues_url(project["id"], uploaded["id"]))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_issues"] == 0
    assert body["items"] == []


def test_repeated_post_does_not_accumulate_duplicates(client, project, db_session):
    uploaded = _upload(client, project, _mixed_content())

    first = client.post(_assessment_url(project["id"], uploaded["id"])).json()
    second = client.post(_assessment_url(project["id"], uploaded["id"])).json()

    assert first == second
    persisted = db_session.scalar(
        select(func.count())
        .select_from(MigrationIssue)
        .where(MigrationIssue.uploaded_file_id == uuid.UUID(uploaded["id"]))
    )
    assert persisted == 3
    assert client.get(_issues_url(project["id"], uploaded["id"])).json()["total_issues"] == 3


def test_assessment_sets_project_status_assessed(client, project):
    uploaded = _upload(client, project, _mixed_content())

    assert client.get(f"{PREFIX}/projects/{project['id']}").json()["status"] == "uploaded"
    client.post(_assessment_url(project["id"], uploaded["id"]))

    assert client.get(f"{PREFIX}/projects/{project['id']}").json()["status"] == "assessed"


def test_unknown_file_returns_404(client, project):
    missing = str(uuid.uuid4())

    assert client.post(_assessment_url(project["id"], missing)).status_code == 404
    assert client.get(_issues_url(project["id"], missing)).status_code == 404


def test_cross_project_file_returns_404(client, project):
    uploaded = _upload(client, project, _mixed_content())
    other = client.post(
        f"{PREFIX}/projects",
        json={"project_name": "Other Project", "client_name": "Other Client"},
    ).json()

    assert client.post(_assessment_url(other["id"], uploaded["id"])).status_code == 404
    assert client.get(_issues_url(other["id"], uploaded["id"])).status_code == 404


def test_incomplete_persisted_records_return_actionable_409(client, project, db_session):
    file_id = uuid.uuid4()
    db_session.add(
        UploadedFile(
            id=file_id,
            project_id=uuid.UUID(project["id"]),
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

    response = client.post(_assessment_url(project["id"], str(file_id)))

    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "ASSESSMENT_DATA_UNAVAILABLE"
    assert "Re-upload" in detail["message"]


def test_existing_upload_profile_and_project_behaviour_unchanged(client, project, db_session):
    """Assessment additions must not disturb the Day 1–2 contracts."""
    uploaded = _upload(client, project, _mixed_content())

    # Upload response shape is unchanged.
    assert set(uploaded) == {
        "id",
        "project_id",
        "file_name",
        "file_category",
        "file_extension",
        "file_size_bytes",
        "row_count",
        "column_count",
        "detected_columns",
        "schema_errors",
        "processing_status",
        "uploaded_at",
    }

    # Profiling still works and reads immutable original data.
    profile = client.get(
        f"{PREFIX}/projects/{project['id']}/files/{uploaded['id']}/profile"
    )
    assert profile.status_code == 200
    assert profile.json()["total_records"] == 2

    # Running assessment leaves original_data immutable while it reads working_data.
    client.post(_assessment_url(project["id"], uploaded["id"]))
    from app.models import MigrationRecord

    originals = db_session.scalars(
        select(MigrationRecord.original_data)
        .where(MigrationRecord.uploaded_file_id == uuid.UUID(uploaded["id"]))
        .order_by(MigrationRecord.source_row_number)
    ).all()
    assert [row["KUNNR"] for row in originals] == ["00001001", "00001002"]

    # Project listing and retrieval endpoints continue to answer.
    assert client.get(f"{PREFIX}/projects").status_code == 200
    assert client.get(f"{PREFIX}/projects/{project['id']}").status_code == 200
