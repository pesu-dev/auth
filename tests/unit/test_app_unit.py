from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.exceptions.authentication import AuthenticationError, UpstreamError

from app.app import _build_arg_parser, app, main

import logging


@pytest.fixture
def client():
    # The lifespan makes no upstream calls, so the real one is safe to enter. `authenticate` is
    # left unpatched so individual tests can patch it themselves.
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
def test_a_profile_field_without_a_value_is_null(mock_authenticate, client):
    """None in the profile is null on the wire, not a missing key."""
    mock_authenticate.return_value = {
        "status": True,
        "message": "Login successful.",
        "profile": {
            "name": "John Doe",
            "semester": None,
            "section": None,
            "campusCode": 1,
            "middleName": None,
            "mobile": "1234567890",
            "dateOfBirth": "2002-01-31",
            "gender": None,
        },
    }

    response = client.post("/authenticate", json={"username": "u", "password": "p", "profile": True})

    assert response.status_code == 200
    # Fields filtered out (or never produced) stay out; requested ones with no value are null
    assert response.json()["profile"] == {
        "name": "John Doe",
        "semester": None,
        "section": None,
        "campusCode": 1,
        "middleName": None,
        "mobile": "1234567890",
        "dateOfBirth": "2002-01-31",
        "gender": None,
    }


@patch("app.app.pesu_academy.authenticate")
def test_no_profile_key_when_no_profile_was_requested(mock_authenticate, client):
    mock_authenticate.return_value = {"status": True, "message": "Login successful."}

    response = client.post("/authenticate", json={"username": "u", "password": "p"})

    assert response.status_code == 200
    assert sorted(response.json()) == ["message", "status", "timestamp"]


@patch("app.app.pesu_academy.authenticate")
def test_authenticate_general_exception(mock_authenticate, client):
    mock_authenticate.side_effect = Exception("Test exception")
    payload = {"username": "testuser", "password": "testpass", "profile": False}
    response = client.post("/authenticate", json=payload)
    assert response.status_code == 500
    data = response.json()
    assert "Internal Server Error" in data["message"]


@patch("app.pesu.httpx2.AsyncClient.get")
@patch("app.pesu.httpx2.AsyncClient.post")
def test_lifespan_makes_no_upstream_calls(mock_post, mock_get, monkeypatch):
    """Startup and shutdown must not touch PESU Academy: there is no token to prefetch any more."""
    from app.metrics.collector import LIFESPAN_EVENTS, MetricsCollector

    collector = MetricsCollector()
    monkeypatch.setattr("app.app.metrics", collector)
    with TestClient(app) as test_client:
        assert test_client.get("/health").status_code == 200

    mock_post.assert_not_called()
    mock_get.assert_not_called()
    snapshot = collector.snapshot()
    assert snapshot.value(LIFESPAN_EVENTS.name, event="startup") == 1.0
    assert snapshot.value(LIFESPAN_EVENTS.name, event="shutdown") == 1.0


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


def test_an_errors_detail_is_logged_but_never_returned(client, caplog):
    """The detail names the user and what PESU answered; the caller only ever sees the documented message."""
    error = UpstreamError(detail="PESU Academy answered the login for user=user with status 503.")
    assert str(error) == "UpstreamError: PESU Academy answered the login for user=user with status 503."
    assert str(UpstreamError()) == f"UpstreamError: {UpstreamError().message}"

    with patch("app.app.pesu_academy.authenticate") as mock_authenticate:
        mock_authenticate.side_effect = error
        with caplog.at_level("ERROR"):
            response = client.post("/authenticate", json={"username": "user", "password": "pass"})

    assert response.json()["message"] == UpstreamError().message
    assert "UpstreamError: PESU Academy answered the login for user=user with status 503." in caplog.text


def test_server_error_is_logged_with_a_traceback(client, caplog):
    """A 5xx is genuinely our problem or the upstream's, so it keeps the stack trace."""
    with patch("app.app.pesu_academy.authenticate") as mock_authenticate:
        mock_authenticate.side_effect = UpstreamError("PESU Academy could not be reached.")
        with caplog.at_level("ERROR"):
            response = client.post("/authenticate", json={"username": "user", "password": "pass"})

    assert response.status_code == 502
    records = [r for r in caplog.records if "UpstreamError" in r.message]
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


def test_an_unreadable_body_is_a_400_in_the_standard_shape(client, monkeypatch, caplog):
    """A JSON body that is not even UTF-8 never reaches validation; FastAPI rejects it first.

    It must still answer in this API's `{status, message, timestamp}` shape, be counted, and never
    echo the bytes it could not read: they could hold a password.
    """
    from app.metrics.collector import ERRORS_BY_TYPE, VALIDATION_ERRORS, MetricsCollector

    collector = MetricsCollector()
    monkeypatch.setattr("app.app.metrics", collector)
    secret = b"hunter2-actual-secret"

    with caplog.at_level("WARNING"):
        response = client.post(
            "/authenticate",
            content=b'{"password": "\xff' + secret + b'"}',
            headers={"Content-Type": "application/json"},
        )

    assert response.status_code == 400
    data = response.json()
    assert sorted(data) == ["message", "status", "timestamp"]
    assert data["status"] is False
    assert data["message"] == "Could not parse request body."
    assert secret.decode() not in caplog.text
    assert secret.decode() not in response.text
    snapshot = collector.snapshot()
    assert snapshot.value(ERRORS_BY_TYPE.name, type="RequestBodyParseError") == 1.0
    assert list(snapshot.samples(VALIDATION_ERRORS.name)) == []


def test_an_unknown_route_is_a_404_in_the_standard_shape(client, monkeypatch, caplog):
    from app.metrics.collector import ERRORS_BY_TYPE, MetricsCollector

    collector = MetricsCollector()
    monkeypatch.setattr("app.app.metrics", collector)

    with caplog.at_level("INFO"):
        response = client.get("/not-a-route-secret-path")

    assert response.status_code == 404
    data = response.json()
    assert sorted(data) == ["message", "status", "timestamp"]
    assert data["status"] is False
    assert data["message"] == "No route matches this path."
    # The path is the caller's, so it is neither echoed nor logged by us
    assert "secret-path" not in response.text
    assert not [r for r in caplog.records if r.name == "root" and "secret-path" in r.getMessage()]
    assert collector.snapshot().value(ERRORS_BY_TYPE.name, type="RouteNotFoundError") == 1.0


@pytest.mark.parametrize(
    "method, path, allow",
    [("POST", "/health", "GET, HEAD"), ("DELETE", "/metrics", "GET, HEAD"), ("GET", "/authenticate", "POST"), ("PUT", "/docs", "GET, HEAD")],
)
def test_an_unsupported_method_is_a_405_in_the_standard_shape(client, monkeypatch, method, path, allow):
    from app.metrics.collector import ERRORS_BY_TYPE, MetricsCollector

    collector = MetricsCollector()
    monkeypatch.setattr("app.app.metrics", collector)

    response = client.request(method, path)

    assert response.status_code == 405
    # Every method the path is served for, HEAD included, not only the first route's
    assert response.headers["allow"] == allow
    data = response.json()
    assert sorted(data) == ["message", "status", "timestamp"]
    assert data["message"] == "This method is not allowed on this path."
    assert collector.snapshot().value(ERRORS_BY_TYPE.name, type="MethodNotAllowedError") == 1.0


@pytest.mark.parametrize("path", ["/health", "/readme", "/metrics"])
def test_head_answers_like_get_without_the_body(client, path):
    get = client.get(path, follow_redirects=False)
    head = client.head(path, follow_redirects=False)

    assert head.status_code == get.status_code
    assert head.headers.get("content-type") == get.headers.get("content-type")
    assert head.headers.get("location") == get.headers.get("location")
    assert head.content == b""


def test_head_routes_stay_out_of_the_schema(client):
    """HEAD answers as GET does, so it is not documented twice."""
    paths = client.get("/openapi.json").json()["paths"]

    assert not [path for path, operations in paths.items() if "head" in operations]


@pytest.mark.asyncio
async def test_any_other_framework_error_gets_the_standard_shape(monkeypatch):
    """Nothing raises another status today; if something starts to, it still answers in the standard shape."""
    import json

    from fastapi import Request
    from starlette.exceptions import HTTPException

    from app.app import http_error_handler
    from app.metrics.collector import MetricsCollector

    # The handler counts the error, so into a collector of this test's own
    monkeypatch.setattr("app.app.metrics", MetricsCollector())
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": [], "query_string": b""})

    response = await http_error_handler(request, HTTPException(status_code=418, detail="Teapot."))

    assert response.status_code == 418
    data = json.loads(response.body)
    assert data["status"] is False
    assert data["message"] == "Teapot."
