"""Integration tests for deterministic data profiling (FR-011–FR-014)."""
import uuid

from sqlalchemy import insert

from app.config import settings
from app.constants.enums import FileCategory, ProcessingStatus, RecordStatus
from app.models import MigrationRecord, UploadedFile


def upload_url(project: dict) -> str:
    return f"{settings.api_prefix}/projects/{project['id']}/files/ecc"


def profile_url(project_id: str, file_id: str) -> str:
    return f"{settings.api_prefix}/projects/{project_id}/files/{file_id}/profile"


def upload_csv(client, project, content: bytes, name: str = "profile.csv") -> dict:
    response = client.post(
        upload_url(project),
        files={"file": (name, content, "text/csv")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def field(profile: dict, name: str) -> dict:
    return next(item for item in profile["fields"] if item["field_name"] == name)


def profiled_content() -> bytes:
    return (
        b"KUNNR,NAME1,ORT01,LAND1,KTOKD,BUKRS,SMTP_ADDR\n"
        b"1,Alpha,Mumbai,IN,ZDOM,1000,a@example.com\n"
        b"2,Beta,Pune,IN,ZDOM,1000,\n"
        b"1,Alpha,Mumbai,IN,ZDOM,1000,a@example.com\n"
        b"3,   ,Delhi,IN,ZDOM,1000,c@example.com\n"
    )


def test_profile_returns_totals_missing_unique_and_completeness(
    client, project
):
    uploaded = upload_csv(client, project, profiled_content())
    response = client.get(profile_url(project["id"], uploaded["id"]))

    assert response.status_code == 200
    profile = response.json()
    assert profile["project_id"] == project["id"]
    assert profile["uploaded_file_id"] == uploaded["id"]
    assert profile["file_name"] == "profile.csv"
    assert profile["total_records"] == 4
    assert profile["total_fields"] == 7
    assert profile["total_missing_values"] == 2
    assert profile["overall_completeness_percentage"] == 92.86

    kunnr = field(profile, "KUNNR")
    assert kunnr == {
        "field_name": "KUNNR",
        "total_records": 4,
        "missing_values": 0,
        "non_missing_values": 4,
        "unique_values": 3,
        "completeness_percentage": 100.0,
    }
    assert field(profile, "NAME1")["missing_values"] == 1
    assert field(profile, "NAME1")["unique_values"] == 2
    assert field(profile, "SMTP_ADDR")["missing_values"] == 1
    assert field(profile, "SMTP_ADDR")["unique_values"] == 2


def test_field_profiles_follow_original_source_column_order(client, project):
    uploaded = upload_csv(client, project, profiled_content())
    profile = client.get(profile_url(project["id"], uploaded["id"])).json()

    assert [item["field_name"] for item in profile["fields"]] == [
        "KUNNR",
        "NAME1",
        "ORT01",
        "LAND1",
        "KTOKD",
        "BUKRS",
        "SMTP_ADDR",
    ]


def test_exact_duplicate_group_identifies_representative_and_duplicate_rows(
    client, project
):
    uploaded = upload_csv(client, project, profiled_content())
    profile = client.get(profile_url(project["id"], uploaded["id"])).json()

    assert profile["exact_duplicate_records"] == 1
    assert profile["exact_duplicate_groups"] == 1
    assert profile["duplicate_groups"] == [
        {
            "representative_row_number": 1,
            "duplicate_row_numbers": [3],
            "record_count": 2,
            "duplicate_count": 1,
        }
    ]


def test_three_identical_rows_count_two_duplicates(client, project):
    content = b"KUNNR,NAME1\n1,Alpha\n1,Alpha\n1,Alpha\n"
    uploaded = upload_csv(client, project, content)
    profile = client.get(profile_url(project["id"], uploaded["id"])).json()

    assert profile["exact_duplicate_records"] == 2
    assert profile["exact_duplicate_groups"] == 1
    assert profile["duplicate_groups"][0]["duplicate_row_numbers"] == [2, 3]


def test_unique_value_counts_exclude_null_and_whitespace(client, project):
    content = b"KUNNR,NAME1\n1,Alpha\n2,\n3,   \n4,Alpha\n"
    uploaded = upload_csv(client, project, content)
    profile = client.get(profile_url(project["id"], uploaded["id"])).json()
    name_profile = field(profile, "NAME1")

    assert name_profile["missing_values"] == 2
    assert name_profile["non_missing_values"] == 2
    assert name_profile["unique_values"] == 1
    assert name_profile["completeness_percentage"] == 50.0


def test_files_with_schema_findings_can_still_be_profiled(client, project):
    content = b"KUNNR,NAME1,UNEXPECTED\n1,Alpha,X\n2,Beta,Y\n"
    uploaded = upload_csv(client, project, content)
    response = client.get(profile_url(project["id"], uploaded["id"]))

    assert uploaded["processing_status"] == "schema_errors"
    assert response.status_code == 200
    assert response.json()["total_records"] == 2
    assert response.json()["total_fields"] == 3


def test_profile_is_scoped_to_the_requested_uploaded_file(client, project):
    first = upload_csv(client, project, b"KUNNR,NAME1\n1,Alpha\n", "first.csv")
    second = upload_csv(
        client,
        project,
        b"KUNNR,NAME1\n2,Beta\n3,Gamma\n",
        "second.csv",
    )

    first_profile = client.get(profile_url(project["id"], first["id"])).json()
    second_profile = client.get(profile_url(project["id"], second["id"])).json()
    assert first_profile["total_records"] == 1
    assert second_profile["total_records"] == 2


def test_unknown_file_returns_404(client, project):
    response = client.get(profile_url(project["id"], str(uuid.uuid4())))

    assert response.status_code == 404
    assert response.json()["detail"] == "Uploaded file not found in this project."


def test_file_from_another_project_returns_404(client, project):
    uploaded = upload_csv(client, project, b"KUNNR,NAME1\n1,Alpha\n")
    other = client.post(
        f"{settings.api_prefix}/projects",
        json={"project_name": "Other Project", "client_name": "Other Client"},
    ).json()

    response = client.get(profile_url(other["id"], uploaded["id"]))
    assert response.status_code == 404


def test_legacy_file_without_migration_records_returns_actionable_409(
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
            row_count=2,
            column_count=2,
            detected_columns=["KUNNR", "NAME1"],
            schema_errors=[],
            processing_status=ProcessingStatus.ACCEPTED,
        )
    )
    db_session.commit()

    response = client.get(profile_url(project["id"], str(file_id)))
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "PROFILE_DATA_UNAVAILABLE"
    assert "Re-upload" in response.json()["detail"]["message"]


def test_incomplete_persisted_record_set_returns_409(client, project, db_session):
    file_id = uuid.uuid4()
    project_id = uuid.UUID(project["id"])
    db_session.add(
        UploadedFile(
            id=file_id,
            project_id=project_id,
            file_name="incomplete.csv",
            file_category=FileCategory.SOURCE_DATA,
            file_extension=".csv",
            file_size_bytes=100,
            storage_path="storage/incomplete.csv",
            row_count=2,
            column_count=2,
            detected_columns=["KUNNR", "NAME1"],
            schema_errors=[],
            processing_status=ProcessingStatus.ACCEPTED,
        )
    )
    db_session.flush()
    db_session.add(
        MigrationRecord(
            project_id=project_id,
            uploaded_file_id=file_id,
            source_row_number=1,
            original_data={"KUNNR": "1", "NAME1": "Alpha"},
            working_data={"KUNNR": "1", "NAME1": "Alpha"},
            record_status=RecordStatus.PENDING,
        )
    )
    db_session.commit()

    response = client.get(profile_url(project["id"], str(file_id)))
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "PROFILE_DATA_UNAVAILABLE"


def test_duplicate_comparison_is_independent_of_json_key_order(
    client, project, db_session
):
    file_id = uuid.uuid4()
    project_id = uuid.UUID(project["id"])
    db_session.add(
        UploadedFile(
            id=file_id,
            project_id=project_id,
            file_name="ordered-json.csv",
            file_category=FileCategory.SOURCE_DATA,
            file_extension=".csv",
            file_size_bytes=100,
            storage_path="storage/ordered-json.csv",
            row_count=2,
            column_count=2,
            detected_columns=["A", "B"],
            schema_errors=[],
            processing_status=ProcessingStatus.ACCEPTED,
        )
    )
    db_session.flush()
    db_session.execute(
        insert(MigrationRecord),
        [
            {
                "id": uuid.uuid4(),
                "project_id": project_id,
                "uploaded_file_id": file_id,
                "source_row_number": 1,
                "original_data": {"A": 1, "B": 2},
                "working_data": {"A": 1, "B": 2},
                "record_status": RecordStatus.PENDING,
            },
            {
                "id": uuid.uuid4(),
                "project_id": project_id,
                "uploaded_file_id": file_id,
                "source_row_number": 2,
                "original_data": {"B": 2, "A": 1},
                "working_data": {"B": 2, "A": 1},
                "record_status": RecordStatus.PENDING,
            },
        ],
    )
    db_session.commit()

    profile = client.get(profile_url(project["id"], str(file_id))).json()
    assert profile["exact_duplicate_records"] == 1


def test_profiling_does_not_modify_original_or_working_data(
    client, project, db_session
):
    uploaded = upload_csv(client, project, b"KUNNR,NAME1\n1,Alpha\n")
    file_id = uuid.UUID(uploaded["id"])
    before = db_session.query(MigrationRecord).filter_by(uploaded_file_id=file_id).one()
    original_before = dict(before.original_data)
    working_before = dict(before.working_data)

    response = client.get(profile_url(project["id"], uploaded["id"]))
    db_session.expire_all()
    after = db_session.query(MigrationRecord).filter_by(uploaded_file_id=file_id).one()

    assert response.status_code == 200
    assert after.original_data == original_before
    assert after.working_data == working_before
