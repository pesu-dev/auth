"""Unit tests for app/app.py — FastAPI application layer."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.app import app, main


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ---------------------------------------------------------------------------
# /authenticate — validation & exception handling
# ---------------------------------------------------------------------------


@patch("app.app.pesu_academy.authenticate")
def test_authenticate_validation_error(mock_authenticate, client, caplog):
    """If pesu_academy returns data that fails ResponseModel validation → 500."""
    mock_authenticate.return_value = {
        "status": True,
        "message": "Login successful",
        "profile": "this should cause validation error",
    }
    payload = {"username": "testuser", "password": "testpass", "profile": False}
    with caplog.at_level("DEBUG"):
        response = client.post("/authenticate", json=payload)
    assert response.status_code == 500
    data = response.json()
    assert "Internal Server Error" in data["message"]
    assert "Validation error on ResponseModel" in caplog.text


@patch("app.app.pesu_academy.authenticate")
def test_authenticate_general_exception(mock_authenticate, client):
    """Unhandled exception from pesu_academy → 500 with generic message."""
    mock_authenticate.side_effect = Exception("Test exception")
    payload = {"username": "testuser", "password": "testpass", "profile": False}
    response = client.post("/authenticate", json=payload)
    assert response.status_code == 500
    data = response.json()
    assert "Internal Server Error" in data["message"]


# ---------------------------------------------------------------------------
# /authenticate — successful mock response
# ---------------------------------------------------------------------------


@patch("app.app.pesu_academy.authenticate")
def test_authenticate_success_mocked(mock_authenticate, client):
    """When pesu_academy returns a valid result the endpoint returns 200."""
    mock_authenticate.return_value = {
        "status": True,
        "message": "Login successful.",
    }
    payload = {"username": "testuser", "password": "testpass"}
    response = client.post("/authenticate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] is True
    assert data["message"] == "Login successful."
    assert "timestamp" in data


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


def test_health_endpoint(client):
    """Health check returns 200 with status=True and message='ok'."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] is True
    assert data["message"] == "ok"
    assert "timestamp" in data


# ---------------------------------------------------------------------------
# /readme
# ---------------------------------------------------------------------------


def test_readme_redirect(client):
    """README endpoint returns 308 redirect to GitHub."""
    response = client.get("/readme", follow_redirects=False)
    assert response.status_code == 308
    assert "github.com" in response.headers["location"]


# ---------------------------------------------------------------------------
# main() CLI function
# ---------------------------------------------------------------------------


@patch("app.app.argparse.ArgumentParser.parse_args")
@patch("app.app.logging.basicConfig")
@patch("app.app.uvicorn.run")
def test_main_function_default_args(mock_run, mock_logging, mock_parse_args):
    mock_args = MagicMock()
    mock_args.host = "0.0.0.0"
    mock_args.port = 5000
    mock_args.debug = False
    mock_parse_args.return_value = mock_args

    main()

    mock_logging.assert_called_once()
    mock_run.assert_called_once_with("app.app:app", host="0.0.0.0", port=5000, reload=False)


@patch("app.app.argparse.ArgumentParser.parse_args")
@patch("app.app.logging.basicConfig")
@patch("app.app.uvicorn.run")
def test_main_function_debug_mode(mock_run, mock_logging, mock_parse_args):
    mock_args = MagicMock()
    mock_args.host = "127.0.0.1"
    mock_args.port = 8000
    mock_args.debug = True
    mock_parse_args.return_value = mock_args

    main()

    mock_logging.assert_called_once()
    mock_run.assert_called_once_with("app.app:app", host="127.0.0.1", port=8000, reload=True)
