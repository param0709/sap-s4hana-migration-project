"""ECC upload validation tests (FR-004 to FR-010)."""
import uuid

import pandas as pd
import pytest

from app.config import settings
from tests.conftest import make_xlsx


def upload_url(project: dict) -> str:
    return f"{settings.api_prefix}/projects/{project['id']}/files/ecc"


def post_file(client, project, name, content, mime="application/octet-stream"):
    return client.post(upload_url(project), files={"file": (name, content, mime)})


# --- Accepted uploads -------------------------------------------------------


def test_valid_excel_upload_returns_metadata_and_no_schema_errors(client, project, valid_ecc_frame):
    response = post_file(client, project, "ECC_Customer_Master.xlsx", make_xlsx(valid_ecc_frame))

    assert response.status_code == 201
    body = response.json()
    assert body["file_name"] == "ECC_Customer_Master.xlsx"
    assert body["row_count"] == 2
    assert body["column_count"] == 8
    assert body["schema_errors"] == []
    assert body["processing_status"] == "accepted"
    assert "KUNNR" in body["detected_columns"]


def test_valid_csv_upload_is_accepted(client, project):
    content = b"KUNNR,NAME1,ORT01,LAND1,KTOKD,BUKRS\n00001001,Alpha,Mumbai,IN,ZDOM,1000\n"

    response = post_file(client, project, "ecc.csv", content, "text/csv")

    assert response.status_code == 201
    body = response.json()
    assert body["row_count"] == 1
    assert body["column_count"] == 6
    assert body["processing_status"] == "accepted"


def test_headers_are_matched_case_insensitively(client, project):
    content = b" kunnr ,name1,ort01,land1,ktokd,bukrs\n1,Alpha,Mumbai,IN,ZDOM,1000\n"

    body = post_file(client, project, "lowercase.csv", content, "text/csv").json()

    assert body["schema_errors"] == []
    assert body["detected_columns"][0] == "KUNNR"


# --- Rejected uploads (hard gate, FR-005) -----------------------------------


@pytest.mark.parametrize(
    ("name", "content", "expected_code"),
    [
        ("notes.txt", b"just some text", "UNSUPPORTED_FILE_TYPE"),
        ("guide.pdf", b"%PDF-1.4", "UNSUPPORTED_FILE_TYPE"),
        ("noextension", b"data", "UNSUPPORTED_FILE_TYPE"),
        ("empty.csv", b"", "EMPTY_FILE"),
        ("headers_only.csv", b"KUNNR,NAME1\n", "NO_DATA_ROWS"),
        ("corrupt.xlsx", b"this is definitely not a workbook", "CORRUPTED_FILE"),
    ],
)
def test_invalid_files_are_rejected(client, project, name, content, expected_code):
    response = post_file(client, project, name, content)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == expected_code


def test_oversized_file_is_rejected(client, project):
    oversized = b"KUNNR\n" + b"x" * (settings.max_upload_bytes + 1)

    response = post_file(client, project, "huge.csv", oversized, "text/csv")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "FILE_TOO_LARGE"


def test_upload_to_unknown_project_returns_404(client, valid_ecc_frame):
    response = client.post(
        f"{settings.api_prefix}/projects/11111111-1111-1111-1111-111111111111/files/ecc",
        files={"file": ("ecc.xlsx", make_xlsx(valid_ecc_frame), "application/octet-stream")},
    )
    assert response.status_code == 404


# --- Schema findings (FR-008, FR-009) ---------------------------------------


def test_missing_required_columns_are_reported(client, project, valid_ecc_frame):
    frame = valid_ecc_frame.drop(columns=["LAND1", "BUKRS"])

    body = post_file(client, project, "missing.xlsx", make_xlsx(frame)).json()

    assert body["processing_status"] == "schema_errors"
    error = next(e for e in body["schema_errors"] if e["code"] == "MISSING_REQUIRED_COLUMNS")
    assert error["severity"] == "critical"
    assert sorted(error["columns"]) == ["BUKRS", "LAND1"]


def test_unexpected_columns_are_reported(client, project, valid_ecc_frame):
    frame = valid_ecc_frame.copy()
    frame["ZZLEGACY_REF"] = "X"

    body = post_file(client, project, "extra.xlsx", make_xlsx(frame)).json()

    error = next(e for e in body["schema_errors"] if e["code"] == "UNEXPECTED_COLUMNS")
    assert error["severity"] == "medium"
    assert error["columns"] == ["ZZLEGACY_REF"]


def test_duplicate_columns_are_reported(client, project):
    content = b"KUNNR,NAME1,ORT01,LAND1,KTOKD,BUKRS,KUNNR\n1,Alpha,Mumbai,IN,ZDOM,1000,1\n"

    body = post_file(client, project, "dupes.csv", content, "text/csv").json()

    error = next(e for e in body["schema_errors"] if e["code"] == "DUPLICATE_COLUMNS")
    assert error["severity"] == "high"
    assert error["columns"] == ["KUNNR"]
    # The duplicate must not also be reported as an unexpected column.
    unexpected = [e for e in body["schema_errors"] if e["code"] == "UNEXPECTED_COLUMNS"]
    assert unexpected == []


def test_file_with_schema_errors_is_still_stored_and_listed(client, project, valid_ecc_frame):
    frame = valid_ecc_frame.drop(columns=["LAND1"])
    post_file(client, project, "missing.xlsx", make_xlsx(frame))

    listed = client.get(f"{settings.api_prefix}/projects/{project['id']}/files").json()

    assert len(listed) == 1
    assert listed[0]["processing_status"] == "schema_errors"


# --- Original file preservation (FR-007) ------------------------------------


def test_stored_original_is_byte_identical(client, project, db_session, valid_ecc_frame):
    from pathlib import Path

    from app.models import UploadedFile

    content = make_xlsx(valid_ecc_frame)
    response = post_file(client, project, "ECC_Customer_Master.xlsx", content)

    record = db_session.get(UploadedFile, uuid.UUID(response.json()["id"]))
    assert Path(record.storage_path).read_bytes() == content


# --- Reference endpoint -----------------------------------------------------


def test_ecc_schema_reference_lists_required_columns(client):
    body = client.get(f"{settings.api_prefix}/reference/ecc-schema").json()

    names = [column["name"] for column in body["required_columns"]]
    assert names == ["KUNNR", "NAME1", "ORT01", "LAND1", "KTOKD", "BUKRS"]
    assert ".csv" in body["allowed_extensions"]


def test_blank_column_header_is_reported(client, project):
    content = b"KUNNR,NAME1,,LAND1,KTOKD,BUKRS\n1,Alpha,x,IN,ZDOM,1000\n"

    body = post_file(client, project, "blank_header.csv", content, "text/csv").json()

    error = next(e for e in body["schema_errors"] if e["code"] == "BLANK_COLUMN_HEADER")
    assert error["severity"] == "high"
    assert error["columns"] == ["column 3"]
    # A blank header is not a duplicate, even if there are several of them.
    assert not any(e["code"] == "DUPLICATE_COLUMNS" for e in body["schema_errors"])


def test_latin1_encoded_csv_is_accepted(client, project):
    content = "KUNNR,NAME1,ORT01,LAND1,KTOKD,BUKRS\n1,Caf\u00e9 Ltd,Mumbai,IN,ZDOM,1000\n".encode(
        "latin-1"
    )

    response = post_file(client, project, "latin1.csv", content, "text/csv")

    assert response.status_code == 201
    assert response.json()["schema_errors"] == []


def test_project_status_becomes_uploaded_after_upload(client, project, valid_ecc_frame):
    assert project["status"] == "draft"

    post_file(client, project, "ECC_Customer_Master.xlsx", make_xlsx(valid_ecc_frame))

    refreshed = client.get(f"{settings.api_prefix}/projects/{project['id']}").json()
    assert refreshed["status"] == "uploaded"


def test_project_status_becomes_uploaded_even_with_schema_findings(
    client, project, valid_ecc_frame
):
    frame = valid_ecc_frame.drop(columns=["LAND1"])

    body = post_file(client, project, "missing.xlsx", make_xlsx(frame)).json()
    assert body["processing_status"] == "schema_errors"

    refreshed = client.get(f"{settings.api_prefix}/projects/{project['id']}").json()
    assert refreshed["status"] == "uploaded"


def test_rejected_upload_leaves_project_in_draft(client, project):
    post_file(client, project, "notes.txt", b"not a spreadsheet")

    refreshed = client.get(f"{settings.api_prefix}/projects/{project['id']}").json()
    assert refreshed["status"] == "draft"


def test_xls_files_are_no_longer_accepted(client, project):
    response = post_file(client, project, "legacy.xls", b"\xd0\xcf\x11\xe0legacy workbook")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "UNSUPPORTED_FILE_TYPE"
