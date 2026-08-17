"""API integration tests for GET .../readiness.

These drive the real HTTP surface through the SQLite test client, covering the
success contract and every documented 404/409 branch. PostgreSQL remains the
runtime database used for live verification.
"""
import uuid

import pytest
from sqlalchemy import select

from app.config import settings
from app.constants.enums import FileCategory, ProcessingStatus
from app.models import UploadedFile

PREFIX = settings.api_prefix

VALID_SAMPLE = (
    b"KUNNR,NAME1,ORT01,LAND1,KTOKD,BUKRS,STCD3,SMTP_ADDR\n"
    b"00001001,Alpha Traders Pvt Ltd,Mumbai,IN,ZDOM,1000,27ABCDE1234F1Z5,sales@alpha.in\n"
    b"00001002,Beta Retail Limited,Delhi,IN,ZDOM,1000,07ABCDE1234F1Z5,info@beta.in\n"
    b"00001003,Global Imports,Dubai,AE,ZINT,1000,,contact@global.ae\n"
)
INVALID_SAMPLE = b"KUNNR,NAME1,LAND1\n00002001,Test Customer,IN\n"


def _upload(client, project, content: bytes, name: str = "readiness.csv") -> dict:
    response = client.post(
        f"{PREFIX}/projects/{project['id']}/files/ecc",
        files={"file": (name, content, "text/csv")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _readiness_url(project_id: str, file_id: str) -> str:
    return f"{PREFIX}/projects/{project_id}/files/{file_id}/readiness"


def _assessment_url(project_id: str, file_id: str) -> str:
    return f"{PREFIX}/projects/{project_id}/files/{file_id}/assessment"


def test_readiness_before_assessment_returns_409_assessment_required(client, project):
    uploaded = _upload(client, project, VALID_SAMPLE)

    response = client.get(_readiness_url(project["id"], uploaded["id"]))

    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "ASSESSMENT_REQUIRED"
    assert "assessment" in detail["message"].lower()


def test_readiness_valid_sample_full_contract(client, project):
    uploaded = _upload(client, project, VALID_SAMPLE)
    client.post(_assessment_url(project["id"], uploaded["id"]))

    response = client.get(_readiness_url(project["id"], uploaded["id"]))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["project_id"] == project["id"]
    assert body["uploaded_file_id"] == uploaded["id"]
    assert body["methodology_version"] == "v1"
    assert body["score"] == 98.96
    assert body["band"] == "ready"
    assert body["migration_ready"] is True
    assert body["critical_blockers"] == 0
    assert body["total_records"] == 3
    assert body["records_ready"] == 3
    assert body["records_needing_review"] == 0
    assert body["total_issues"] == 0

    components = body["components"]
    assert set(components) == {
        "schema_conformity",
        "data_completeness",
        "record_readiness",
        "issue_severity",
    }
    assert components["schema_conformity"]["score"] == 100
    assert components["data_completeness"]["score"] == 95.83
    assert components["record_readiness"]["score"] == 100
    assert components["issue_severity"]["score"] == 100
    # Weights are exposed and total 1.00.
    assert round(sum(c["weight"] for c in components.values()), 2) == 1.00
    for component in components.values():
        assert 0 <= component["score"] <= 100
        assert 0 <= component["weighted_score"] <= 100


def test_readiness_invalid_sample_blocked(client, project):
    uploaded = _upload(client, project, INVALID_SAMPLE)
    client.post(_assessment_url(project["id"], uploaded["id"]))

    body = client.get(_readiness_url(project["id"], uploaded["id"])).json()

    assert body["score"] == 48.00
    assert body["band"] == "blocked"
    assert body["migration_ready"] is False
    assert body["critical_blockers"] == 5
    assert body["components"]["schema_conformity"]["score"] == 55
    assert body["components"]["issue_severity"]["score"] == 60


def test_readiness_unknown_file_returns_404(client, project):
    assert (
        client.get(_readiness_url(project["id"], str(uuid.uuid4()))).status_code == 404
    )


def test_readiness_cross_project_file_returns_404(client, project):
    uploaded = _upload(client, project, VALID_SAMPLE)
    client.post(_assessment_url(project["id"], uploaded["id"]))
    other = client.post(
        f"{PREFIX}/projects",
        json={"project_name": "Other", "client_name": "Other Client"},
    ).json()

    assert (
        client.get(_readiness_url(other["id"], uploaded["id"])).status_code == 404
    )


def test_readiness_incomplete_records_returns_409_data_unavailable(
    client, project, db_session
):
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
            row_count=3,
            column_count=8,
            detected_columns=["KUNNR", "NAME1"],
            schema_errors=[],
            processing_status=ProcessingStatus.ACCEPTED,
        )
    )
    db_session.commit()

    response = client.get(_readiness_url(project["id"], str(file_id)))

    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "READINESS_DATA_UNAVAILABLE"
    assert "Re-upload" in detail["message"]


def test_repeated_readiness_requests_are_identical(client, project):
    uploaded = _upload(client, project, VALID_SAMPLE)
    client.post(_assessment_url(project["id"], uploaded["id"]))

    first = client.get(_readiness_url(project["id"], uploaded["id"])).json()
    second = client.get(_readiness_url(project["id"], uploaded["id"])).json()

    assert first == second


def test_existing_profile_and_assessment_apis_unchanged(client, project):
    """Readiness must not alter the existing profile/assessment/issues contracts."""
    uploaded = _upload(client, project, VALID_SAMPLE)

    profile = client.get(
        f"{PREFIX}/projects/{project['id']}/files/{uploaded['id']}/profile"
    ).json()
    assert profile["total_records"] == 3
    assert profile["total_fields"] == 8
    assert profile["overall_completeness_percentage"] == 95.83

    summary = client.post(_assessment_url(project["id"], uploaded["id"])).json()
    assert set(summary) == {
        "project_id",
        "uploaded_file_id",
        "total_records",
        "records_ready",
        "records_needing_review",
        "total_issues",
        "issues_by_severity",
        "issues_by_rule",
    }

    issues = client.get(
        f"{PREFIX}/projects/{project['id']}/files/{uploaded['id']}/issues"
    ).json()
    assert issues["total_issues"] == 0
    assert issues["items"] == []
