import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.app import _csrf_token_refresh_loop, app, main


@pytest.fixture
def client():
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
@patch("app.app._refresh_csrf_token_with_lock")
async def test_csrf_token_refresh_loop_logs_exception_on_failure(mock_refresh, mock_sleep, caplog):
    mock_refresh.side_effect = RuntimeError("Simulated CSRF refresh failure")
    mock_sleep.side_effect = asyncio.CancelledError

    with caplog.at_level("ERROR"):
        with pytest.raises(asyncio.CancelledError):
            await _csrf_token_refresh_loop()

    assert "Failed to refresh unauthenticated CSRF token in the background." in caplog.text


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
