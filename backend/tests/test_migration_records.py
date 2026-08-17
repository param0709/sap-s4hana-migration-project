"""Day 2 coverage for durable, lossless migration-record ingestion."""
import io
import uuid
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from openpyxl import Workbook
from sqlalchemy import func, select

from app.config import settings
from app.constants.enums import RecordStatus
from app.models import MigrationRecord, UploadedFile
from app.services import file_service
from tests.conftest import make_xlsx


def upload_url(project: dict) -> str:
    return f"{settings.api_prefix}/projects/{project['id']}/files/ecc"


def post_file(client, project, name, content, mime="application/octet-stream"):
    return client.post(upload_url(project), files={"file": (name, content, mime)})


def records_for(db_session, file_id: str | uuid.UUID) -> list[MigrationRecord]:
    uploaded_file_id = uuid.UUID(file_id) if isinstance(file_id, str) else file_id
    return list(
        db_session.scalars(
            select(MigrationRecord)
            .where(MigrationRecord.uploaded_file_id == uploaded_file_id)
            .order_by(MigrationRecord.source_row_number)
        ).all()
    )


def table_count(db_session, model) -> int:
    return db_session.scalar(select(func.count()).select_from(model)) or 0


def workbook_bytes(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()


def test_csv_upload_persists_one_record_per_data_row(client, project, db_session):
    content = (
        b"KUNNR,NAME1,ORT01,LAND1,KTOKD,BUKRS\n"
        b"1,Alpha,Mumbai,IN,ZDOM,1000\n"
        b"2,Beta,Pune,IN,ZDOM,1000\n"
        b"3,Gamma,Delhi,IN,ZDOM,1000\n"
    )
    response = post_file(client, project, "ecc.csv", content, "text/csv")

    assert response.status_code == 201
    assert len(records_for(db_session, response.json()["id"])) == 3


def test_xlsx_upload_persists_one_record_per_data_row(
    client, project, db_session, valid_ecc_frame
):
    response = post_file(client, project, "ecc.xlsx", make_xlsx(valid_ecc_frame))

    assert response.status_code == 201
    assert len(records_for(db_session, response.json()["id"])) == 2


def test_records_link_to_project_and_uploaded_file(client, project, db_session):
    content = b"KUNNR,NAME1,ORT01,LAND1,KTOKD,BUKRS\n1,Alpha,Mumbai,IN,ZDOM,1000\n"
    file_id = post_file(client, project, "ecc.csv", content).json()["id"]

    record = records_for(db_session, file_id)[0]
    assert str(record.project_id) == project["id"]
    assert str(record.uploaded_file_id) == file_id


def test_source_order_and_initial_status_are_preserved(client, project, db_session):
    content = (
        b"KUNNR,NAME1,ORT01,LAND1,KTOKD,BUKRS\n"
        b"first,Alpha,Mumbai,IN,ZDOM,1000\n"
        b"second,Beta,Pune,IN,ZDOM,1000\n"
        b"third,Gamma,Delhi,IN,ZDOM,1000\n"
    )
    file_id = post_file(client, project, "ordered.csv", content).json()["id"]
    records = records_for(db_session, file_id)

    assert [record.source_row_number for record in records] == [2, 3, 4]
    assert [record.original_data["KUNNR"] for record in records] == [
        "first",
        "second",
        "third",
    ]
    assert all(record.record_status == RecordStatus.PENDING for record in records)


def test_source_row_numbers_include_header_and_blank_rows(client, project, db_session):
    response = post_file(
        client,
        project,
        "blank-row.csv",
        b"KUNNR,NAME1,ORT01,LAND1,KTOKD,BUKRS\n"
        b",,,,,\n"
        b"00001001,Alpha,Mumbai,IN,ZDOM,1000\n",
        "text/csv",
    )

    assert response.status_code == 201
    records = records_for(db_session, response.json()["id"])
    assert [record.source_row_number for record in records] == [3]


def test_original_and_working_data_start_equal_but_independent(
    client, project, db_session
):
    content = b"KUNNR,NAME1,ORT01,LAND1,KTOKD,BUKRS\n1,Alpha,Mumbai,IN,ZDOM,1000\n"
    file_id = post_file(client, project, "copies.csv", content).json()["id"]
    record = records_for(db_session, file_id)[0]

    assert record.original_data == record.working_data
    assert record.original_data is not record.working_data
    record.working_data["KUNNR"] = "CHANGED"
    assert record.original_data["KUNNR"] == "1"


def test_headers_are_normalised_for_record_keys(client, project, db_session):
    content = b" kunnr ,Name1,ort01,LAND1,ktokd,bukrs\n1,Alpha,Mumbai,IN,ZDOM,1000\n"
    file_id = post_file(client, project, "headers.csv", content).json()["id"]

    assert set(records_for(db_session, file_id)[0].original_data) == {
        "KUNNR",
        "NAME1",
        "ORT01",
        "LAND1",
        "KTOKD",
        "BUKRS",
    }


def test_csv_empty_cells_become_json_null(client, project, db_session):
    content = b"KUNNR,NAME1,ORT01,LAND1,KTOKD,BUKRS\n1,,Mumbai,IN,ZDOM,1000\n"
    file_id = post_file(client, project, "null.csv", content).json()["id"]

    assert records_for(db_session, file_id)[0].original_data["NAME1"] is None


def test_xlsx_dates_are_iso_serialised(client, project, db_session):
    frame = pd.DataFrame(
        {
            "KUNNR": ["1"],
            "NAME1": ["Alpha"],
            "ORT01": ["Mumbai"],
            "LAND1": ["IN"],
            "KTOKD": ["ZDOM"],
            "BUKRS": ["1000"],
            "ERDAT": [pd.Timestamp("2024-04-10")],
        }
    )
    file_id = post_file(client, project, "dates.xlsx", make_xlsx(frame)).json()["id"]

    assert records_for(db_session, file_id)[0].original_data["ERDAT"] == (
        "2024-04-10T00:00:00"
    )


def test_duplicate_header_values_are_both_preserved(client, project, db_session):
    content = (
        b"KUNNR,NAME1,ORT01,LAND1,KTOKD,BUKRS,KUNNR\n"
        b"first,Alpha,Mumbai,IN,ZDOM,1000,second\n"
    )
    response = post_file(client, project, "duplicates.csv", content)
    record = records_for(db_session, response.json()["id"])[0]

    assert response.json()["processing_status"] == "schema_errors"
    assert record.original_data["KUNNR"] == "first"
    assert record.original_data["KUNNR__DUPLICATE_2"] == "second"


def test_blank_header_values_do_not_overwrite_each_other(client, project, db_session):
    content = b"KUNNR,,,BUKRS\n1,left,right,1000\n"
    file_id = post_file(client, project, "blanks.csv", content).json()["id"]
    record = records_for(db_session, file_id)[0]

    assert record.original_data["__BLANK_COLUMN_2"] == "left"
    assert record.original_data["__BLANK_COLUMN_3"] == "right"


def test_schema_findings_do_not_prevent_row_persistence(
    client, project, db_session, valid_ecc_frame
):
    response = post_file(
        client,
        project,
        "missing.xlsx",
        make_xlsx(valid_ecc_frame.drop(columns=["LAND1"])),
    )

    assert response.json()["processing_status"] == "schema_errors"
    assert len(records_for(db_session, response.json()["id"])) == 2


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("notes.txt", b"not a spreadsheet"),
        ("headers.csv", b"KUNNR,NAME1\n"),
        ("broken.xlsx", b"not an xlsx file"),
    ],
)
def test_hard_gate_rejections_create_no_database_rows(
    client, project, db_session, name, content
):
    response = post_file(client, project, name, content)

    assert response.status_code == 422
    assert table_count(db_session, UploadedFile) == 0
    assert table_count(db_session, MigrationRecord) == 0


def test_blank_csv_rows_are_not_persisted(client, project, db_session):
    content = (
        b"KUNNR,NAME1,ORT01,LAND1,KTOKD,BUKRS\n"
        b"1,Alpha,Mumbai,IN,ZDOM,1000\n"
        b"\n"
        b"   ,  , , , , \n"
        b"2,Beta,Pune,IN,ZDOM,1000\n"
        b"\n\n"
    )
    response = post_file(client, project, "blank_rows.csv", content)
    records = records_for(db_session, response.json()["id"])

    assert response.json()["row_count"] == 2
    assert [record.original_data["KUNNR"] for record in records] == ["1", "2"]


def test_partially_blank_csv_row_is_preserved(client, project, db_session):
    content = b"KUNNR,NAME1,ORT01,LAND1,KTOKD,BUKRS\n1,,Mumbai,IN,,1000\n"
    file_id = post_file(client, project, "partial.csv", content).json()["id"]

    assert len(records_for(db_session, file_id)) == 1


def test_blank_xlsx_rows_are_not_persisted(client, project, db_session):
    content = workbook_bytes(
        [
            ["KUNNR", "NAME1", "ORT01", "LAND1", "KTOKD", "BUKRS"],
            ["1", "Alpha", "Mumbai", "IN", "ZDOM", "1000"],
            [None, None, None, None, None, None],
            ["   ", "", None, " ", None, ""],
            ["2", "Beta", "Pune", "IN", "ZDOM", "1000"],
        ]
    )
    response = post_file(client, project, "blank_rows.xlsx", content)

    assert response.json()["row_count"] == 2
    records = records_for(db_session, response.json()["id"])
    assert [record.source_row_number for record in records] == [2, 5]


def test_nonblank_extra_csv_cell_is_rejected_without_persistence(
    client, project, db_session
):
    content = b"KUNNR,NAME1\n1,Alpha,UNDECLARED\n"
    response = post_file(client, project, "wide.csv", content)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "MALFORMED_ROW"
    assert table_count(db_session, UploadedFile) == 0
    assert table_count(db_session, MigrationRecord) == 0


def test_nonblank_extra_xlsx_cell_is_rejected_without_persistence(
    client, project, db_session
):
    content = workbook_bytes(
        [
            ["KUNNR", "NAME1"],
            ["1", "Alpha", "UNDECLARED"],
        ]
    )
    response = post_file(client, project, "wide.xlsx", content)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "MALFORMED_ROW"
    assert table_count(db_session, UploadedFile) == 0
    assert table_count(db_session, MigrationRecord) == 0


def test_trailing_empty_csv_cells_are_harmless(client, project, db_session):
    content = b"KUNNR,NAME1\n1,Alpha,,\n"
    response = post_file(client, project, "trailing_empty.csv", content)

    assert response.status_code == 201
    assert len(records_for(db_session, response.json()["id"])) == 1


def test_valid_quoted_and_multiline_csv_values_are_preserved(
    client, project, db_session
):
    content = (
        b"KUNNR,NAME1,ORT01,LAND1,KTOKD,BUKRS\n"
        b'1,"Alpha, Traders","Mumbai\nWest",IN,ZDOM,1000\n'
    )
    file_id = post_file(client, project, "quoted.csv", content).json()["id"]
    record = records_for(db_session, file_id)[0]

    assert record.original_data["NAME1"] == "Alpha, Traders"
    assert record.original_data["ORT01"] == "Mumbai\nWest"


def test_malformed_csv_quoting_is_rejected(client, project, db_session):
    content = b'KUNNR,NAME1\n1,"Alpha\n'
    response = post_file(client, project, "malformed.csv", content)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "CORRUPTED_FILE"
    assert table_count(db_session, MigrationRecord) == 0


def test_second_upload_keeps_each_files_records_separate(client, project, db_session):
    first = b"KUNNR,NAME1\n1,Alpha\n"
    second = b"KUNNR,NAME1\n2,Beta\n3,Gamma\n"
    first_id = post_file(client, project, "first.csv", first).json()["id"]
    second_id = post_file(client, project, "second.csv", second).json()["id"]

    assert len(records_for(db_session, first_id)) == 1
    assert len(records_for(db_session, second_id)) == 2


def test_uploaded_row_count_matches_persisted_record_count(
    client, project, db_session, valid_ecc_frame
):
    response = post_file(client, project, "count.xlsx", make_xlsx(valid_ecc_frame))
    file_id = uuid.UUID(response.json()["id"])
    uploaded_file = db_session.get(UploadedFile, file_id)

    assert uploaded_file.row_count == len(records_for(db_session, file_id))


def test_upload_response_shape_remains_unchanged(client, project, valid_ecc_frame):
    body = post_file(client, project, "shape.xlsx", make_xlsx(valid_ecc_frame)).json()

    assert set(body) == {
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


class RecordingSession:
    """Small session double for transaction-order and rollback tests."""

    def __init__(self, fail_at: str | None = None):
        self.fail_at = fail_at
        self.events: list[str] = []
        self.project = SimpleNamespace(status="draft")

    def _record(self, event: str) -> None:
        self.events.append(event)
        if self.fail_at == event:
            raise RuntimeError(f"failure at {event}")

    def add(self, value) -> None:
        self._record("add")

    def get(self, model, object_id):
        self._record("get")
        return self.project

    def flush(self) -> None:
        self._record("flush")

    def execute(self, statement, mappings) -> None:
        self._record("execute")

    def commit(self) -> None:
        self._record("commit")

    def rollback(self) -> None:
        self.events.append("rollback")

    def refresh(self, value) -> None:
        self._record("refresh")


def prepare_service_double(monkeypatch, session: RecordingSession) -> None:
    monkeypatch.setattr(file_service, "store_original", lambda *args: "storage/source.csv")
    monkeypatch.setattr(
        file_service,
        "remove_original",
        lambda path: session.events.append("cleanup"),
    )

    def mark_uploaded(db, project):
        session.events.append("mark")
        project.status = "uploaded"
        return project

    monkeypatch.setattr(file_service.project_service, "mark_uploaded", mark_uploaded)


def test_transaction_order_flushes_parent_before_bulk_insert(monkeypatch):
    session = RecordingSession()
    prepare_service_double(monkeypatch, session)
    content = b"KUNNR,NAME1\n1,Alpha\n"

    file_service.ingest_ecc_file(
        session,
        uuid.uuid4(),
        "ordered.csv",
        content,
    )

    assert session.events == [
        "add",
        "get",
        "mark",
        "flush",
        "execute",
        "commit",
        "refresh",
    ]


@pytest.mark.parametrize("failure", ["flush", "execute", "commit"])
def test_database_failures_rollback_and_reraise(monkeypatch, failure):
    session = RecordingSession(fail_at=failure)
    prepare_service_double(monkeypatch, session)
    content = b"KUNNR,NAME1\n1,Alpha\n"

    with pytest.raises(RuntimeError, match=f"failure at {failure}"):
        file_service.ingest_ecc_file(
            session,
            uuid.uuid4(),
            "failure.csv",
            content,
        )

    assert session.events[-2:] == ["rollback", "cleanup"]
    assert "refresh" not in session.events


def test_database_failure_removes_the_written_original(monkeypatch):
    session = RecordingSession(fail_at="flush")
    project_id = uuid.uuid4()
    project_directory = Path(settings.storage_dir) / str(project_id)

    with pytest.raises(RuntimeError, match="failure at flush"):
        file_service.ingest_ecc_file(
            session,
            project_id,
            "orphan.csv",
            b"KUNNR,NAME1\n1,Alpha\n",
        )

    assert not project_directory.exists()
