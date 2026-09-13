"""Tests for the optional bearer token on /metrics.

Every test here pins `METRICS_TOKEN` explicitly rather than inheriting it from the environment.
tests/conftest.py calls load_dotenv() before this module imports app.app, so a METRICS_TOKEN in a
local .env would otherwise start returning 401 to every other /metrics test in the suite -- the
same class of silent, environment-dependent breakage as the ".env vanished" case.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.app import app
from app.exceptions.authentication import AuthenticationError
from app.metrics.collector import MetricsCollector

TOKEN = "test-metrics-token"


@pytest.fixture
def client(monkeypatch):
    """A client with a fresh collector and no token configured."""
    monkeypatch.setattr("app.app.metrics", MetricsCollector())
    monkeypatch.setattr("app.metrics.auth.METRICS_TOKEN", None)
    with (
        patch("app.app.pesu_academy.prefetch_client_with_csrf_token", new_callable=AsyncMock),
        patch("app.app.pesu_academy.close_client", new_callable=AsyncMock),
    ):
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client


@pytest.fixture
def protected(client, monkeypatch):
    """The same client, with a token required."""
    monkeypatch.setattr("app.metrics.auth.METRICS_TOKEN", TOKEN)
    return client


@pytest.mark.parametrize("query", ["", "?fmt=json", "?fmt=prometheus"])
def test_open_when_no_token_is_configured(client, query):
    """The default deployment, and what every existing caller and the Docker instructions expect."""
    assert client.get(f"/metrics{query}").status_code == 200


@pytest.mark.parametrize("query", ["", "?fmt=json", "?fmt=prometheus"])
def test_the_right_token_is_accepted_in_either_format(protected, query):
    response = protected.get(f"/metrics{query}", headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 200


@pytest.mark.parametrize(
    ("label", "headers"),
    [
        ("no header at all", {}),
        ("the wrong token", {"Authorization": "Bearer not-the-token"}),
        ("a prefix of the token", {"Authorization": f"Bearer {TOKEN[:-1]}"}),
        ("the token without its scheme", {"Authorization": TOKEN}),
        ("basic instead of bearer", {"Authorization": "Basic dXNlcjpwYXNz"}),
        # HTTPBasic would raise HTTPException on this one, answering in Starlette's shape and
        # skipping errors_total; HTTPBearer rejects the scheme before that can happen.
        ("malformed basic credentials", {"Authorization": "Basic !!!!"}),
        ("an empty bearer value", {"Authorization": "Bearer "}),
    ],
)
def test_rejected_without_the_token(protected, label, headers):
    response = protected.get("/metrics", headers=headers)
    assert response.status_code == 401, label


def test_the_rejection_is_shaped_like_every_other_error(protected):
    """A 401 here must not be Starlette's {"detail": ...}, which is what HTTPBasic would produce."""
    response = protected.get("/metrics")
    body = response.json()
    assert set(body) == {"status", "message", "timestamp"}
    assert body["status"] is False
    assert body["message"] == "Invalid or missing metrics token."


def test_the_rejection_says_how_to_authenticate(protected):
    """Required of a 401, and it tells a scraper "wrong credentials" from "none wanted"."""
    assert protected.get("/metrics").headers["www-authenticate"] == "Bearer"


def test_the_json_format_is_protected_too(protected):
    """The format selector must not be a way around the token."""
    assert protected.get("/metrics?fmt=json").status_code == 401


def test_a_rejection_is_counted_as_an_error_and_a_client_fault(protected):
    """The middleware/handler split from the metrics work still holds for this new error."""
    protected.get("/metrics")
    body = protected.get("/metrics?fmt=json", headers={"Authorization": f"Bearer {TOKEN}"}).json()
    assert body["errorsByType"] == {"MetricsAuthorizationError": 1}
    assert body["responsesByStatus"]["401"] == 1
    assert body["failuresByFault"] == {"client": 1}


def test_health_is_not_protected(protected):
    """Render's own health check and the cron-job.org monitors send no credentials."""
    assert protected.get("/health").status_code == 200


def test_an_empty_environment_variable_counts_as_unset(monkeypatch):
    """A variable declared but left blank must not lock everyone out of the endpoint."""
    monkeypatch.setenv("METRICS_TOKEN", "")
    import importlib

    import app.metrics.auth as metrics_auth

    importlib.reload(metrics_auth)
    assert metrics_auth.METRICS_TOKEN is None
    monkeypatch.delenv("METRICS_TOKEN")
    importlib.reload(metrics_auth)


def test_other_errors_carry_no_stray_headers(client):
    """Regression on adding `headers` to PESUAcademyError: it is None for everything else."""
    with patch("app.app.pesu_academy.authenticate", new_callable=AsyncMock) as authenticate:
        authenticate.side_effect = AuthenticationError("Invalid username or password.")
        response = client.post("/authenticate", json={"username": "PES1201800001", "password": "x"})
    assert response.status_code == 401
    assert "www-authenticate" not in response.headers
