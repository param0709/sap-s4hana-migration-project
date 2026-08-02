"""Unit/integration tests for the deterministic readiness methodology v1.

These exercise the calculation service directly against SQLite-backed fixtures.
The sample byte contents mirror sample-data/valid_ecc_customers.csv and
sample-data/invalid_ecc_customers.csv so the documented expected values are
locked in.
"""
import copy
import uuid

import pytest
from sqlalchemy import func, select

from app.config import settings
from app.constants.enums import (
    FileCategory,
    ProcessingStatus,
    ReadinessBand,
    RecordStatus,
)
from app.models import MigrationIssue, MigrationRecord, UploadedFile
from app.services import assessment_service, readiness_service

VALID_SAMPLE = (
    b"KUNNR,NAME1,ORT01,LAND1,KTOKD,BUKRS,STCD3,SMTP_ADDR\n"
    b"00001001,Alpha Traders Pvt Ltd,Mumbai,IN,ZDOM,1000,27ABCDE1234F1Z5,sales@alpha.in\n"
    b"00001002,Beta Retail Limited,Delhi,IN,ZDOM,1000,07ABCDE1234F1Z5,info@beta.in\n"
    b"00001003,Global Imports,Dubai,AE,ZINT,1000,,contact@global.ae\n"
)

INVALID_SAMPLE = b"KUNNR,NAME1,LAND1\n00002001,Test Customer,IN\n"


def _upload(client, project, content: bytes, name: str = "readiness.csv") -> dict:
    response = client.post(
        f"{settings.api_prefix}/projects/{project['id']}/files/ecc",
        files={"file": (name, content, "text/csv")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _assess(db_session, project: dict, file_id: str) -> None:
    assessment_service.assess_file(
        db_session, uuid.UUID(project["id"]), uuid.UUID(file_id)
    )


def _readiness(db_session, project: dict, file_id: str) -> dict:
    return readiness_service.calculate_readiness(
        db_session, uuid.UUID(project["id"]), uuid.UUID(file_id)
    )


def _records(db_session, file_id: str) -> list[MigrationRecord]:
    return list(
        db_session.scalars(
            select(MigrationRecord)
            .where(MigrationRecord.uploaded_file_id == uuid.UUID(file_id))
            .order_by(MigrationRecord.source_row_number)
        ).all()
    )


# 1. Methodology weights total exactly 1.00.
def test_component_weights_total_one():
    assert round(sum(readiness_service.COMPONENT_WEIGHTS.values()), 2) == 1.00
    assert set(readiness_service.COMPONENT_WEIGHTS) == {
        "schema_conformity",
        "data_completeness",
        "record_readiness",
        "issue_severity",
    }


# 2. Every component stays between 0 and 100.
def test_all_component_scores_within_bounds(client, project, db_session):
    for content in (VALID_SAMPLE, INVALID_SAMPLE):
        uploaded = _upload(client, project, content, name=f"{uuid.uuid4()}.csv")
        _assess(db_session, project, uploaded["id"])
        result = _readiness(db_session, project, uploaded["id"])
        for component in result["components"].values():
            assert 0 <= component["score"] <= 100
            assert 0 <= component["weighted_score"] <= 100
        assert 0 <= result["score"] <= 100


# 3. Valid sample calculation produces the documented values.
def test_valid_sample_scores(client, project, db_session):
    uploaded = _upload(client, project, VALID_SAMPLE)
    _assess(db_session, project, uploaded["id"])

    result = _readiness(db_session, project, uploaded["id"])
    components = result["components"]

    assert components["schema_conformity"]["score"] == 100
    assert components["data_completeness"]["score"] == 95.83
    assert components["record_readiness"]["score"] == 100
    assert components["issue_severity"]["score"] == 100
    assert result["score"] == 98.96
    assert result["band"] == ReadinessBand.READY
    assert result["migration_ready"] is True
    assert result["critical_blockers"] == 0
    assert result["total_records"] == 3
    assert result["records_ready"] == 3
    assert result["records_needing_review"] == 0
    assert result["total_issues"] == 0


# 4. Invalid sample calculation produces the documented values.
def test_invalid_sample_scores(client, project, db_session):
    uploaded = _upload(client, project, INVALID_SAMPLE)
    _assess(db_session, project, uploaded["id"])

    result = _readiness(db_session, project, uploaded["id"])
    components = result["components"]

    assert components["schema_conformity"]["score"] == 55
    assert components["data_completeness"]["score"] == 100
    assert components["record_readiness"]["score"] == 0
    assert components["issue_severity"]["score"] == 90
    assert result["score"] == 54.00
    assert result["band"] == ReadinessBand.BLOCKED
    assert result["migration_ready"] is False
    # One critical schema finding (MISSING_REQUIRED_COLUMNS) + one critical BR-004.
    assert result["critical_blockers"] == 2


# 5. Critical blockers prevent ready even when the numeric score exceeds 90.
def test_critical_blocker_forces_blocked_over_high_score(client, project, db_session):
    rows = [b"KUNNR,NAME1,ORT01,LAND1,KTOKD,BUKRS,STCD3,SMTP_ADDR\n"]
    # Row 1: Indian customer missing GSTIN -> critical BR-004.
    rows.append(b"1,Alpha,Mumbai,IN,ZDOM,1000,,a1@example.in\n")
    # Rows 2-10: valid non-Indian customers with every field populated.
    for i in range(2, 11):
        rows.append(
            f"{i},Name{i},City,AE,ZINT,1000,NA{i},user{i}@example.ae\n".encode()
        )
    uploaded = _upload(client, project, b"".join(rows), name="blocker.csv")
    _assess(db_session, project, uploaded["id"])

    result = _readiness(db_session, project, uploaded["id"])

    assert result["score"] >= 90
    assert result["critical_blockers"] == 1
    assert result["band"] == ReadinessBand.BLOCKED
    assert result["migration_ready"] is False


# 6. Band-boundary behaviour of the pure band selector.
@pytest.mark.parametrize(
    ("score", "blockers", "expected"),
    [
        (100.0, 1, ReadinessBand.BLOCKED),
        (10.0, 2, ReadinessBand.BLOCKED),
        (90.0, 0, ReadinessBand.READY),
        (89.99, 0, ReadinessBand.MINOR_REMEDIATION),
        (75.0, 0, ReadinessBand.MINOR_REMEDIATION),
        (74.99, 0, ReadinessBand.AT_RISK),
        (50.0, 0, ReadinessBand.AT_RISK),
        (49.99, 0, ReadinessBand.NOT_READY),
        (0.0, 0, ReadinessBand.NOT_READY),
    ],
)
def test_band_boundaries(score, blockers, expected):
    assert readiness_service._band(score, blockers) == expected


# 7. No-assessment state raises AssessmentRequiredError.
def test_pending_records_require_assessment(client, project, db_session):
    uploaded = _upload(client, project, VALID_SAMPLE)

    with pytest.raises(
        readiness_service.AssessmentRequiredError, match="[Rr]un assessment"
    ):
        _readiness(db_session, project, uploaded["id"])


# 8 & 9. Unknown / cross-project files return None (the route maps that to 404).
def test_unknown_and_cross_project_file_returns_none(client, project, db_session):
    uploaded = _upload(client, project, VALID_SAMPLE)
    _assess(db_session, project, uploaded["id"])
    other = client.post(
        f"{settings.api_prefix}/projects",
        json={"project_name": "Other", "client_name": "Other Client"},
    ).json()

    assert (
        readiness_service.calculate_readiness(
            db_session, uuid.UUID(project["id"]), uuid.uuid4()
        )
        is None
    )
    assert (
        readiness_service.calculate_readiness(
            db_session, uuid.UUID(other["id"]), uuid.UUID(uploaded["id"])
        )
        is None
    )


# 10. Incomplete persisted-record data raises an actionable error.
def test_incomplete_records_raise_data_unavailable(client, project, db_session):
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

    with pytest.raises(
        readiness_service.ReadinessDataUnavailableError, match="Re-upload"
    ):
        readiness_service.calculate_readiness(
            db_session, uuid.UUID(project["id"]), file_id
        )


# 11. Readiness never mutates data, statuses, issues or project state.
def test_readiness_does_not_mutate_state(client, project, db_session):
    uploaded = _upload(client, project, INVALID_SAMPLE)
    _assess(db_session, project, uploaded["id"])

    before_records = [
        (
            copy.deepcopy(r.original_data),
            copy.deepcopy(r.working_data),
            r.record_status,
        )
        for r in _records(db_session, uploaded["id"])
    ]
    before_issues = db_session.scalar(
        select(func.count()).select_from(MigrationIssue)
    )
    before_status = client.get(
        f"{settings.api_prefix}/projects/{project['id']}"
    ).json()["status"]

    _readiness(db_session, project, uploaded["id"])
    db_session.expire_all()

    after_records = [
        (r.original_data, r.working_data, r.record_status)
        for r in _records(db_session, uploaded["id"])
    ]
    assert after_records == before_records
    assert (
        db_session.scalar(select(func.count()).select_from(MigrationIssue))
        == before_issues
    )
    assert (
        client.get(f"{settings.api_prefix}/projects/{project['id']}").json()["status"]
        == before_status
    )


# 12. Reassessment after corrected working data updates readiness.
def test_readiness_updates_after_corrected_working_data(client, project, db_session):
    content = (
        b"KUNNR,NAME1,ORT01,LAND1,KTOKD,BUKRS,STCD3,SMTP_ADDR\n"
        b"1,Alpha,Mumbai,IN,ZDOM,1000,27ABCDE1234F1Z5,a@example.in\n"
        b"2,Beta,Pune,IN,ZDOM,1000,27ABCDE1234F1Z5,bad-email\n"
    )
    uploaded = _upload(client, project, content)
    _assess(db_session, project, uploaded["id"])
    before = _readiness(db_session, project, uploaded["id"])
    assert before["total_issues"] == 1
    assert before["records_needing_review"] == 1

    record = _records(db_session, uploaded["id"])[1]
    record.working_data = {**record.working_data, "SMTP_ADDR": "beta@example.in"}
    db_session.commit()
    _assess(db_session, project, uploaded["id"])

    after = _readiness(db_session, project, uploaded["id"])
    assert after["total_issues"] == 0
    assert after["records_needing_review"] == 0
    assert after["score"] > before["score"]
    assert after["band"] == ReadinessBand.READY


# 14. Zero-record defensive behaviour.
def test_zero_records_treated_as_unavailable(client, project, db_session):
    file_id = uuid.uuid4()
    db_session.add(
        UploadedFile(
            id=file_id,
            project_id=uuid.UUID(project["id"]),
            file_name="empty.csv",
            file_category=FileCategory.SOURCE_DATA,
            file_extension=".csv",
            file_size_bytes=10,
            storage_path="storage/empty.csv",
            row_count=0,
            column_count=8,
            detected_columns=["KUNNR"],
            schema_errors=[],
            processing_status=ProcessingStatus.ACCEPTED,
        )
    )
    db_session.commit()

    with pytest.raises(readiness_service.ReadinessDataUnavailableError):
        readiness_service.calculate_readiness(
            db_session, uuid.UUID(project["id"]), file_id
        )


# 15. Repeated calls return identical results and perform no writes.
def test_repeated_readiness_is_identical_and_write_free(client, project, db_session):
    uploaded = _upload(client, project, VALID_SAMPLE)
    _assess(db_session, project, uploaded["id"])

    first = _readiness(db_session, project, uploaded["id"])
    second = _readiness(db_session, project, uploaded["id"])

    assert first == second
    assert not db_session.new
    assert not db_session.dirty
    assert not db_session.deleted
