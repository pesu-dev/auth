from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.app import APP_ENVIRONMENT, app, resolve_environment


def test_resolve_environment_defaults_when_unset(monkeypatch):
    monkeypatch.delenv("PESU_AUTH_ENVIRONMENT", raising=False)
    assert resolve_environment() == "development"


def test_resolve_environment_defaults_when_empty(monkeypatch):
    monkeypatch.setenv("PESU_AUTH_ENVIRONMENT", "")
    assert resolve_environment() == "development"


@pytest.mark.parametrize("value", ["development", "staging", "production"])
def test_resolve_environment_accepts_allowed_values(value):
    assert resolve_environment(value) == value


def test_resolve_environment_rejects_invalid_values():
    with pytest.raises(ValueError, match="PESU_AUTH_ENVIRONMENT"):
        resolve_environment("prod")


def test_module_environment_is_one_of_the_allowed_values():
    assert APP_ENVIRONMENT in {"development", "staging", "production"}


@pytest.fixture
def client():
    with (
        patch("app.app.pesu_academy.prefetch_client_with_csrf_token", new_callable=AsyncMock),
        patch("app.app.pesu_academy.close_client", new_callable=AsyncMock),
        patch("app.app.pesu_academy.is_csrf_cache_ready", return_value=True),
    ):
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client


def test_health_includes_version_environment_and_checks(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] is True
    assert data["message"] == "ok"
    assert "timestamp" in data
    assert data["version"]
    assert data["environment"] in {"development", "staging", "production"}
    assert set(data["checks"]) == {"csrfCacheReady", "csrfRefreshTaskRunning"}
    assert data["checks"]["csrfRefreshTaskRunning"] is True


def test_health_reports_csrf_cache_not_ready():
    with (
        patch("app.app.pesu_academy.prefetch_client_with_csrf_token", new_callable=AsyncMock),
        patch("app.app.pesu_academy.close_client", new_callable=AsyncMock),
        patch("app.app.pesu_academy.is_csrf_cache_ready", return_value=False),
    ):
        with TestClient(app, raise_server_exceptions=False) as test_client:
            data = test_client.get("/health").json()
    assert data["checks"]["csrfCacheReady"] is False
    assert data["status"] is True


def test_health_reports_refresh_task_not_running():
    finished = MagicMock()
    finished.done.return_value = True
    with (
        patch("app.app.pesu_academy.prefetch_client_with_csrf_token", new_callable=AsyncMock),
        patch("app.app.pesu_academy.close_client", new_callable=AsyncMock),
        patch("app.app.pesu_academy.is_csrf_cache_ready", return_value=True),
    ):
        with TestClient(app, raise_server_exceptions=False) as test_client:
            app.state.csrf_refresh_task = finished
            data = test_client.get("/health").json()
    assert data["checks"]["csrfRefreshTaskRunning"] is False
    assert data["status"] is True
