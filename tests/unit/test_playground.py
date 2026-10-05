"""Tests for the custom API explorer."""

from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.app import app


@contextmanager
def _client():
    with (
        patch("app.app.pesu_academy.prefetch_client_with_csrf_token", new_callable=AsyncMock),
        patch("app.app.pesu_academy.close_client", new_callable=AsyncMock),
        TestClient(app, raise_server_exceptions=False) as client,
    ):
        yield client


def test_root_serves_the_custom_api_explorer():
    with _client() as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "PESUAuth API Explorer" in response.text
    assert "Theme" in response.text
    assert "Reload endpoints" in response.text
    assert "Example request" in response.text
    assert "Swagger UI" not in response.text


def test_playground_does_not_pollute_the_public_openapi_schema():
    schema = app.openapi()
    assert "/" not in schema["paths"]
    assert "/ai/explain" not in schema["paths"]

def test_root_returns_html():
    with _client() as client:
        response = client.get("/")
    assert response.headers["content-type"].startswith("text/html")


def test_openapi_json_is_served_without_the_explorer_route():
    with _client() as client:
        response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["openapi"].startswith("3.")
    assert "/" not in schema["paths"]


def test_builtin_docs_are_disabled():
    with _client() as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404


def test_api_routes_still_respond():
    with _client() as client:
        assert client.get("/health").status_code == 200
        assert client.get("/metrics").status_code == 200
        assert client.get("/readme", follow_redirects=False).status_code == 308
        assert client.post("/authenticate", json={}).status_code == 400


def test_metrics_declares_bearer_security_for_the_explorer():
    schema = app.openapi()
    assert schema["paths"]["/metrics"]["get"].get("security")
    assert not schema["paths"]["/health"]["get"].get("security")
