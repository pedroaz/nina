from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from nina_core.integrations import load_credentials


def test_list_integrations_requires_auth(api_client: TestClient) -> None:
    response = api_client.get("/integrations")
    assert response.status_code == 401


def test_list_integrations_returns_known_names(
    api_client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = api_client.get("/integrations", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    names = {entry["name"] for entry in payload["integrations"]}
    assert {"confluence", "jira", "slack", "teams"}.issubset(names)
    for entry in payload["integrations"]:
        assert entry["configured"] is False
        assert entry["status"] == "not_configured"
        assert entry["last_test"] is None


def test_get_unknown_integration_returns_404(
    api_client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = api_client.get("/integrations/does-not-exist", headers=auth_headers)
    assert response.status_code == 404


def test_get_known_unconfigured_integration(
    api_client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = api_client.get("/integrations/slack", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "slack"
    assert data["configured"] is False


def test_test_unconfigured_returns_not_configured(
    api_client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = api_client.post("/integrations/slack/test", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "not_configured"
    # The history endpoint should now return exactly one row.
    history = api_client.get("/integrations/slack/tests?limit=10", headers=auth_headers).json()
    assert len(history["tests"]) == 1
    assert history["tests"][0]["status"] == "not_configured"


def test_test_unknown_integration_returns_404(
    api_client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = api_client.post("/integrations/ghost/test", headers=auth_headers)
    assert response.status_code == 404


def test_credentials_roundtrip(api_client: TestClient, auth_headers: dict[str, str]) -> None:
    payload = {
        "credentials": {
            "base_url": "https://example.atlassian.net",
            "email": "a@b",
            "api_token": "tok",
        }
    }
    response = api_client.put(
        "/integrations/confluence/credentials",
        headers=auth_headers,
        json=payload,
    )
    assert response.status_code == 200
    # GET back the configured-field shape (no secrets).
    config_response = api_client.get("/integrations/confluence/credentials", headers=auth_headers)
    assert config_response.status_code == 200
    fields = config_response.json()["configured_fields"]
    assert fields == {"base_url": True, "email": True, "api_token": True}
    assert {field["name"] for field in config_response.json()["credential_fields"]} == {
        "base_url",
        "email",
        "api_token",
    }
    integration_response = api_client.get("/integrations/confluence", headers=auth_headers)
    assert integration_response.status_code == 200
    integration = integration_response.json()
    assert integration["configured"] is True
    assert integration["configured_fields"] == fields
    # DELETE removes the credentials.
    delete_response = api_client.delete(
        "/integrations/confluence/credentials", headers=auth_headers
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] is True
    after = api_client.get("/integrations/confluence/credentials", headers=auth_headers)
    assert after.json()["configured_fields"] == {}


def test_credentials_merge_preserves_existing_fields(
    api_client: TestClient, auth_headers: dict[str, str], isolated_config: Path
) -> None:
    response = api_client.put(
        "/integrations/confluence/credentials",
        headers=auth_headers,
        json={
            "credentials": {
                "base_url": "https://example.atlassian.net",
                "email": "a@b",
                "api_token": "old",
            }
        },
    )
    assert response.status_code == 200

    merge_response = api_client.put(
        "/integrations/confluence/credentials",
        headers=auth_headers,
        json={"credentials": {"api_token": "new"}, "merge": True},
    )
    assert merge_response.status_code == 200
    assert load_credentials("confluence", config_dir=isolated_config) == {
        "base_url": "https://example.atlassian.net",
        "email": "a@b",
        "api_token": "new",
    }


def test_credentials_rejects_empty_object(
    api_client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = api_client.put(
        "/integrations/jira/credentials",
        headers=auth_headers,
        json={"credentials": {}},
    )
    assert response.status_code == 400


def test_credentials_rejects_unknown_integration(
    api_client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = api_client.put(
        "/integrations/ghost/credentials",
        headers=auth_headers,
        json={"credentials": {"x": 1}},
    )
    assert response.status_code == 404
