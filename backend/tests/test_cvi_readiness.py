"""Day 5 API coverage for deterministic CVI and BP readiness."""

from app.config import settings

PREFIX = settings.api_prefix

VALID_SAMPLE = (
    b"KUNNR,NAME1,ORT01,LAND1,KTOKD,BUKRS,STCD3,SMTP_ADDR,PSTLZ\n"
    b"00001001,Alpha Traders,Mumbai,IN,ZDOM,1000,27ABCDE1234F1Z5,sales@alpha.in,400050\n"
    b"00001002,Beta Exports,Dubai,AE,ZEXP,2000,,info@beta.ae,Dubai\n"
)


def _upload(client, project, content: bytes = VALID_SAMPLE) -> dict:
    response = client.post(
        f"{PREFIX}/projects/{project['id']}/files/ecc",
        files={"file": ("cvi.csv", content, "text/csv")},
    )
    assert response.status_code == 201
    return response.json()


def _assessment_url(project_id: str, file_id: str) -> str:
    return f"{PREFIX}/projects/{project_id}/files/{file_id}/assessment"


def _cvi_url(project_id: str, file_id: str) -> str:
    return f"{PREFIX}/projects/{project_id}/files/{file_id}/cvi-readiness"


def test_cvi_readiness_requires_completed_assessment(client, project):
    uploaded = _upload(client, project)

    response = client.get(_cvi_url(project["id"], uploaded["id"]))

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "ASSESSMENT_REQUIRED"


def test_valid_file_is_cvi_ready_with_bp_configuration(client, project):
    uploaded = _upload(client, project)
    client.post(_assessment_url(project["id"], uploaded["id"]))

    response = client.get(_cvi_url(project["id"], uploaded["id"]))

    assert response.status_code == 200
    body = response.json()
    assert body["methodology_version"] == "v1"
    assert body["status"] == "ready"
    assert body["cvi_ready"] is True
    assert body["records_ready"] == 2
    assert body["records_blocked"] == 0
    assert body["failed_checks"] == 0
    assert body["critical_blockers"] == 0
    assert body["bp_category"] == {"code": "2", "label": "Organization"}
    assert body["required_bp_roles"] == ["FLCU00"]
    assert body["mapped_account_groups"] == [
        {"ecc_account_group": "ZDOM", "bp_grouping": "ZDOM", "record_count": 1},
        {"ecc_account_group": "ZEXP", "bp_grouping": "ZEXP", "record_count": 1},
    ]
    assert all(check["status"] == "passed" for check in body["checks"])
    assert "not an official SAP" in body["disclaimer"]


def test_unmapped_account_group_blocks_cvi(client, project):
    content = VALID_SAMPLE.replace(b"ZDOM,1000", b"ZUNK,1000")
    uploaded = _upload(client, project, content)
    client.post(_assessment_url(project["id"], uploaded["id"]))

    body = client.get(_cvi_url(project["id"], uploaded["id"])).json()

    assert body["cvi_ready"] is False
    assert body["status"] == "blocked"
    assert body["records_blocked"] == 1
    assert body["unmapped_account_groups"] == [
        {"ecc_account_group": "ZUNK", "record_count": 1, "source_rows": [2]}
    ]
    mapping_check = next(check for check in body["checks"] if check["check_id"] == "CVI-001")
    assert mapping_check["status"] == "failed"
    assert mapping_check["affected_source_rows"] == [2]


def test_duplicate_customer_numbers_fail_identity_and_clearance_checks(client, project):
    content = VALID_SAMPLE.replace(b"00001002,Beta", b"00001001,Beta")
    uploaded = _upload(client, project, content)
    client.post(_assessment_url(project["id"], uploaded["id"]))

    body = client.get(_cvi_url(project["id"], uploaded["id"])).json()
    checks = {check["check_id"]: check for check in body["checks"]}

    assert checks["CVI-005"]["affected_source_rows"] == [2, 3]
    assert checks["CVI-006"]["affected_source_rows"] == [2, 3]
    assert body["records_ready"] == 0


def test_required_value_gaps_block_day4_and_day5_readiness(client, project):
    content = (
        b"KUNNR,NAME1,ORT01,LAND1,KTOKD,BUKRS,STCD3\n"
        b"00001001,Alpha,,,,,27ABCDE1234F1Z5\n"
    )
    uploaded = _upload(client, project, content)

    assessment = client.post(_assessment_url(project["id"], uploaded["id"])).json()
    day4 = client.get(
        f"{PREFIX}/projects/{project['id']}/files/{uploaded['id']}/readiness"
    ).json()
    day5 = client.get(_cvi_url(project["id"], uploaded["id"])).json()

    assert assessment["issues_by_rule"] == {
        "BR-011": 1,
        "BR-012": 1,
        "BR-013": 1,
        "BR-014": 1,
    }
    assert day4["migration_ready"] is False
    assert day4["band"] == "blocked"
    assert day5["cvi_ready"] is False


def test_cvi_result_is_repeatable_and_read_only(client, project):
    uploaded = _upload(client, project)
    client.post(_assessment_url(project["id"], uploaded["id"]))

    first = client.get(_cvi_url(project["id"], uploaded["id"])).json()
    second = client.get(_cvi_url(project["id"], uploaded["id"])).json()

    assert first == second


def test_cvi_unknown_and_cross_project_files_return_404(client, project):
    uploaded = _upload(client, project)
    other = client.post(
        f"{PREFIX}/projects",
        json={"project_name": "Other Project", "client_name": "Other Client"},
    ).json()

    assert client.get(_cvi_url(project["id"], "00000000-0000-0000-0000-000000000000")).status_code == 404
    assert client.get(_cvi_url(other["id"], uploaded["id"])).status_code == 404


def test_cvi_reference_exposes_demo_customizing(client):
    response = client.get(f"{PREFIX}/reference/cvi")

    assert response.status_code == 200
    body = response.json()
    assert body["target_object"] == "SAP S/4HANA Business Partner"
    assert body["account_group_mappings"]["ZDOM"] == "ZDOM"
    assert body["required_bp_roles"] == ["FLCU00"]
