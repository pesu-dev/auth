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
    assert "Endpoint explanation" in response.text
    assert "Swagger UI" not in response.text


def test_playground_does_not_pollute_the_public_openapi_schema():
    schema = app.openapi()
    assert "/" not in schema["paths"]
    assert "/ai/explain" not in schema["paths"]