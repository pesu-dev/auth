import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.exceptions.authentication import AuthenticationError, CSRFTokenError

from app.app import _build_arg_parser, _csrf_token_refresh_loop, _refresh_csrf_token, app, main

import logging


@pytest.fixture
def client():
    # Patch the prefetch/close so entering the real lifespan does not hit the network. Without
    # this, every test using this fixture makes a live request to pesuacademy.com. `authenticate`
    # is deliberately left unpatched so individual tests can still patch it themselves.
    with (
        patch("app.app.pesu_academy.prefetch_client_with_csrf_token", new_callable=AsyncMock),
        patch("app.app.pesu_academy.close_client", new_callable=AsyncMock),
    ):
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client


@patch("app.app.pesu_academy.authenticate")
def test_authenticate_validation_error(mock_authenticate, client, caplog):
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
    mock_authenticate.side_effect = Exception("Test exception")
    payload = {"username": "testuser", "password": "testpass", "profile": False}
    response = client.post("/authenticate", json=payload)
    assert response.status_code == 500
    data = response.json()
    assert "Internal Server Error" in data["message"]


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
@patch("app.app._refresh_csrf_token")
async def test_csrf_token_refresh_loop_logs_exception_on_failure(mock_refresh, mock_sleep, caplog):
    mock_refresh.side_effect = RuntimeError("Simulated CSRF refresh failure")
    # The loop sleeps before its first refresh, so let the first sleep pass and stop it on the next
    mock_sleep.side_effect = [None, asyncio.CancelledError]

    with caplog.at_level("ERROR"):
        with pytest.raises(asyncio.CancelledError):
            await _csrf_token_refresh_loop()

    assert "Failed to refresh unauthenticated CSRF token in the background." in caplog.text


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
@patch("app.app._refresh_csrf_token")
async def test_csrf_token_refresh_loop_waits_before_its_first_refresh(mock_refresh, mock_sleep):
    """lifespan has already primed the cache when this task starts.

    Refreshing immediately fetched a second token and discarded the one just prefetched -- an extra
    upstream round trip on every startup. Caught by the new upstream metrics showing two csrf_fetch
    calls on an idle process.
    """
    mock_sleep.side_effect = asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await _csrf_token_refresh_loop()

    mock_refresh.assert_not_awaited()


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
@patch("app.app._refresh_csrf_token")
async def test_csrf_token_refresh_loop_records_a_successful_refresh(mock_refresh, mock_sleep, monkeypatch):
    from app.metrics.collector import CSRF_REFRESHES, MetricsCollector

    collector = MetricsCollector()
    monkeypatch.setattr("app.app.metrics", collector)
    mock_sleep.side_effect = [None, asyncio.CancelledError]

    with pytest.raises(asyncio.CancelledError):
        await _csrf_token_refresh_loop()

    mock_refresh.assert_awaited_once()
    assert collector.snapshot().value(CSRF_REFRESHES.name, outcome="success") == 1.0


def test_lifespan_logs_a_refresh_task_that_refuses_to_cancel(caplog):
    """A background task that fails its own cancellation is reported, not swallowed at shutdown."""

    async def stubborn_loop():
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            raise RuntimeError("refresh task refused to cancel")

    with (
        patch("app.app.pesu_academy.prefetch_client_with_csrf_token", new_callable=AsyncMock),
        patch("app.app.pesu_academy.close_client", new_callable=AsyncMock) as mock_close,
        patch("app.app._csrf_token_refresh_loop", stubborn_loop),
        caplog.at_level("ERROR"),
    ):
        with TestClient(app) as test_client:
            assert test_client.get("/health").status_code == 200

    assert "Failed to cancel unauthenticated CSRF token refresh background task." in caplog.text
    # Shutdown must carry on past the failure and still close the client
    mock_close.assert_awaited_once()


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

    mock_logging.assert_called_once_with(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(filename)s:%(funcName)s:%(lineno)d - %(message)s",
    )
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

    mock_logging.assert_called_once_with(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(filename)s:%(funcName)s:%(lineno)d - %(message)s",
    )
    mock_run.assert_called_once_with("app.app:app", host="127.0.0.1", port=8000, reload=True)

def test_parser_default_port(monkeypatch):
    monkeypatch.delenv("PORT",raising=False)

    parser = _build_arg_parser()
    args = parser.parse_args([])

    assert args.port == 5000

def test_parser_port_from_env(monkeypatch):
    monkeypatch.setenv("PORT", "8080")

    parser = _build_arg_parser()
    args = parser.parse_args([])

    assert args.port == 8080

def test_parser_cli_port_overrides_env(monkeypatch):
    monkeypatch.setenv("PORT", "8080")

    parser = _build_arg_parser()
    args = parser.parse_args(["--port", "9000"])

    assert args.port == 9000

def test_parser_invalid_port(monkeypatch):
    monkeypatch.setenv("PORT", "abc")

    parser = _build_arg_parser()

    with pytest.raises(SystemExit):
        parser.parse_args([])

@pytest.mark.asyncio
@patch("app.app.pesu_academy.prefetch_client_with_csrf_token", new_callable=AsyncMock)
async def test_refresh_csrf_token_delegates_to_pesu_academy(mock_prefetch, caplog):
    """The refresh helper must delegate to PESUAcademy and report success."""
    with caplog.at_level("INFO"):
        await _refresh_csrf_token()

    mock_prefetch.assert_awaited_once()
    assert "Unauthenticated CSRF token refreshed successfully." in caplog.text


@pytest.fixture
def mocked_pesu_client():
    """A TestClient whose PESUAcademy singleton is mocked, so lifespan makes no network calls."""
    with patch("app.app.pesu_academy", new_callable=AsyncMock) as mock_pesu:
        mock_pesu.authenticate.return_value = {
            "status": True,
            "message": "Login successful.",
        }
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client, mock_pesu


def test_authenticate_does_not_trigger_additional_prefetch(mocked_pesu_client):
    """The endpoint must not kick off its own CSRF prefetch; app/pesu.py already does one."""
    client, mock_pesu = mocked_pesu_client
    # Snapshot rather than assert an absolute count: lifespan startup and the periodic
    # refresh loop both legitimately prefetch, and their scheduling is not deterministic.
    before = mock_pesu.prefetch_client_with_csrf_token.await_count

    response = client.post("/authenticate", json={"username": "user", "password": "pass"})

    assert response.status_code == 200
    # Starlette runs background tasks before TestClient returns, so any endpoint-level
    # prefetch would already be counted here.
    assert mock_pesu.prefetch_client_with_csrf_token.await_count == before


def test_client_error_is_logged_without_a_traceback(client, caplog):
    """A 4xx is an expected outcome, so it must be logged at WARNING with no stack trace."""
    with patch("app.app.pesu_academy.authenticate") as mock_authenticate:
        mock_authenticate.side_effect = AuthenticationError("Invalid username or password.")
        with caplog.at_level("WARNING"):
            response = client.post("/authenticate", json={"username": "user", "password": "wrong"})

    assert response.status_code == 401
    records = [r for r in caplog.records if "AuthenticationError" in r.message]
    assert records, "the 401 should still be logged"
    assert all(r.levelname == "WARNING" for r in records)
    # The point of the change: no traceback attached to a routine wrong password
    assert all(r.exc_info is None for r in records)


def test_server_error_is_logged_with_a_traceback(client, caplog):
    """A 5xx is genuinely our problem or the upstream's, so it keeps the stack trace."""
    with patch("app.app.pesu_academy.authenticate") as mock_authenticate:
        mock_authenticate.side_effect = CSRFTokenError("CSRF token could not be extracted.")
        with caplog.at_level("ERROR"):
            response = client.post("/authenticate", json={"username": "user", "password": "pass"})

    assert response.status_code == 502
    records = [r for r in caplog.records if "CSRFTokenError" in r.message]
    assert records, "the 502 should be logged"
    assert all(r.levelname == "ERROR" for r in records)
    assert any(r.exc_info is not None for r in records)


def test_validation_error_is_logged_without_a_traceback(client, caplog):
    """A malformed request is the caller's mistake, so no stack trace either."""
    with caplog.at_level("WARNING"):
        response = client.post("/authenticate", json={"password": "no username here"})

    assert response.status_code == 400
    records = [r for r in caplog.records if "could not be validated" in r.message]
    assert records, "the 400 should still be logged"
    assert all(r.levelname == "WARNING" for r in records)
    assert all(r.exc_info is None for r in records)


def test_validation_error_never_logs_submitted_values(client, caplog):
    """A validation failure must never write the submitted password into the logs.

    `RequestValidationError.errors()` includes an "input" key which, for a missing required
    field, is the whole request body -- so logging the errors verbatim leaks the password.
    """
    secret = "hunter2-actual-secret"

    with caplog.at_level("WARNING"):
        response = client.post("/authenticate", json={"password": secret})

    assert response.status_code == 400
    assert secret not in caplog.text, "the submitted password must not reach the logs"
    assert secret not in response.text, "the submitted password must not reach the response"
    # The diagnostic value is kept: which field, and why
    assert "username" in caplog.text
    assert "Field required" in caplog.text
