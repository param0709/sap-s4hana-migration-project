"""Create-project and list-project API tests (FR-001, FR-002, FR-003)."""
from app.config import settings

ENDPOINT = f"{settings.api_prefix}/projects"


def test_create_project_returns_draft_status_and_project_code(client):
    response = client.post(
        ENDPOINT,
        json={
            "project_name": "Customer Master Wave 1",
            "client_name": "Northwind India",
            "country": "in",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "draft"
    assert body["project_code"].startswith("MIG-")
    assert body["country"] == "IN"
    assert body["migration_object"] == "Customer Master"
    assert body["id"]


def test_project_codes_are_unique_and_sequential(client):
    first = client.post(ENDPOINT, json={"project_name": "Wave 1", "client_name": "Acme"}).json()
    second = client.post(ENDPOINT, json={"project_name": "Wave 2", "client_name": "Acme"}).json()

    assert first["project_code"] != second["project_code"]
    assert int(second["project_code"].split("-")[-1]) == int(first["project_code"].split("-")[-1]) + 1


def test_create_project_rejects_missing_client_name(client):
    response = client.post(ENDPOINT, json={"project_name": "Wave 1"})
    assert response.status_code == 422


def test_create_project_rejects_too_short_name(client):
    response = client.post(ENDPOINT, json={"project_name": "A", "client_name": "Acme"})
    assert response.status_code == 422


def test_list_projects_returns_newest_first(client):
    client.post(ENDPOINT, json={"project_name": "Wave 1", "client_name": "Acme"})
    client.post(ENDPOINT, json={"project_name": "Wave 2", "client_name": "Acme"})

    response = client.get(ENDPOINT)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    assert {item["project_name"] for item in body["items"]} == {"Wave 1", "Wave 2"}


def test_list_projects_is_empty_before_any_are_created(client):
    body = client.get(ENDPOINT).json()
    assert body == {"total": 0, "items": []}


def test_get_unknown_project_returns_404(client):
    response = client.get(f"{ENDPOINT}/11111111-1111-1111-1111-111111111111")
    assert response.status_code == 404


def test_create_project_rejects_whitespace_only_project_name(client):
    response = client.post(ENDPOINT, json={"project_name": "     ", "client_name": "Acme"})
    assert response.status_code == 422


def test_create_project_rejects_whitespace_only_client_name(client):
    response = client.post(ENDPOINT, json={"project_name": "Wave 1", "client_name": "   "})
    assert response.status_code == 422


def test_create_project_strips_surrounding_whitespace(client):
    body = client.post(
        ENDPOINT,
        json={"project_name": "  Wave 1  ", "client_name": "  Acme  ", "country": " in "},
    ).json()

    assert body["project_name"] == "Wave 1"
    assert body["client_name"] == "Acme"
    assert body["country"] == "IN"
