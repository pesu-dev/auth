"""/authenticate end to end: a real request through the whole app, with PESU Academy mocked on the wire.

The other unit tests check PESUAcademy and the route separately. These check what a caller actually
receives -- status code, body and headers -- for each thing PESU Academy can do, and that metrics
and logs record it.
"""

from datetime import datetime, timedelta

import httpx2
import pytest
from fastapi.testclient import TestClient

from app.app import app
from app.exceptions.authentication import ProfileFetchError, ProfileParseError, UpstreamError
from app.metrics.collector import MetricsCollector
from app.models import ResponseModel
from app.pesu import DISPATCHER_URL, LOGIN_URL

IST = timedelta(hours=5, minutes=30)
FULL_PROFILE = {
    "name": "JOHN DOE",
    "prn": "PES2202500001",
    "srn": "PES2UG25CS001",
    "program": "Bachelor of Technology",
    "branch": "Computer Science and Engineering",
    "semester": "Sem-4",
    "section": "Section C",
    "email": "john.doe@example.com",
    "phone": "9876543210",
    "campusCode": 2,
    "campus": "EC",
}


@pytest.fixture
def collector(monkeypatch):
    fresh = MetricsCollector()
    monkeypatch.setattr("app.app.metrics", fresh)
    monkeypatch.setattr("app.app.pesu_academy._metrics", fresh)
    return fresh


@pytest.fixture
def client(collector):
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def pesu_up(wire, make_response, login_payload, profile_payload):
    """PESU Academy answering both calls successfully. Tests edit the payloads before calling."""
    wire.routes[LOGIN_URL] = lambda request: make_response(json=login_payload)
    wire.routes[DISPATCHER_URL] = lambda request: make_response(json=profile_payload)
    return wire


def _authenticate(client, **body):
    return client.post("/authenticate", json={"username": "user", "password": "pass", **body})


def _assert_error_body(response, status):
    body = response.json()
    assert response.status_code == status
    assert set(body) == {"status", "message", "timestamp"}
    assert body["status"] is False
    assert datetime.fromisoformat(body["timestamp"]).utcoffset() == IST
    # The documented error shape, which callers are told to parse with ResponseModel
    ResponseModel.model_validate(body)
    return body


# --- Success ---


def test_a_login_without_a_profile(client, pesu_up):
    response = _authenticate(client)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"status", "message", "timestamp"}
    assert body["status"] is True
    assert body["message"] == "Login successful."
    assert datetime.fromisoformat(body["timestamp"]).utcoffset() == IST
    # No profile asked for, so no profile call
    assert len(pesu_up.requests) == 1


def test_a_login_with_the_full_profile(client, pesu_up):
    response = _authenticate(client, profile=True)

    assert response.status_code == 200
    assert response.json()["profile"] == FULL_PROFILE
    assert len(pesu_up.requests) == 2


def test_a_profile_with_missing_values_returns_null(client, pesu_up, login_payload):
    """What a graduated student looks like on the wire: every field present, the empty ones null."""
    login_payload["mobileJsonObject"].update(className=None, sectionName="NA")

    profile = _authenticate(client, profile=True).json()["profile"]

    assert list(profile) == list(FULL_PROFILE)
    assert profile["semester"] is None
    assert profile["section"] is None


def test_requested_fields_only_and_null_when_empty(client, pesu_up, login_payload):
    login_payload["mobileJsonObject"]["className"] = None

    profile = _authenticate(client, profile=True, fields=["semester", "campusCode", "name"]).json()["profile"]

    assert profile == {"name": "JOHN DOE", "semester": None, "campusCode": 2}


def test_fields_without_profile_return_no_profile(client, pesu_up):
    body = _authenticate(client, profile=False, fields=["name"]).json()

    assert "profile" not in body
    assert len(pesu_up.requests) == 1


def test_the_username_is_sent_without_surrounding_whitespace(client, pesu_up):
    _authenticate(client, username="  PES2UG25CS001\n")

    assert b"PES2UG25CS001\r\n" in pesu_up.requests[0].content
    assert b"  PES2UG25CS001" not in pesu_up.requests[0].content


# --- Failures ---


def test_rejected_credentials(client, wire, make_response, collector):
    wire.routes[LOGIN_URL] = lambda request: make_response(401, json={"statusCode": 401})

    body = _assert_error_body(_authenticate(client, profile=True), 401)

    assert body["message"] == "Invalid username or password, or user does not exist for user=user."
    metrics = client.get("/metrics?fmt=json").json()
    assert metrics["errorsByType"] == {"AuthenticationError": 1}
    assert metrics["upstream"]["login"]["responsesByStatus"] == {"401": 1}
    assert metrics["authenticationResults"] == {"failure": 1}


@pytest.mark.parametrize(
    "reply",
    [
        lambda request: httpx2.Response(500, content=b"<html>error</html>"),
        lambda request: httpx2.Response(302, headers={"location": "https://elsewhere.example/"}),
        lambda request: httpx2.Response(200, content=b"<html>maintenance</html>"),
        lambda request: httpx2.ConnectError("refused", request=request),
    ],
    ids=["server error", "redirect", "not json", "unreachable"],
)
def test_a_login_pesu_cannot_complete_is_a_502(client, wire, collector, reply):
    wire.routes[LOGIN_URL] = reply

    _assert_error_body(_authenticate(client), 502)

    assert client.get("/metrics?fmt=json").json()["errorsByType"] == {UpstreamError.__name__: 1}


def test_a_failed_profile_call_is_a_502(client, pesu_up, collector):
    pesu_up.routes[DISPATCHER_URL] = lambda request: httpx2.Response(503)

    _assert_error_body(_authenticate(client, profile=True), 502)

    metrics = client.get("/metrics?fmt=json").json()
    assert metrics["errorsByType"] == {ProfileFetchError.__name__: 1}
    assert metrics["upstream"]["profile_fetch"]["responsesByStatus"] == {"503": 1}


def test_an_unparseable_profile_is_a_422(client, pesu_up, profile_payload, collector):
    del profile_payload["STUDENT_INFO"]
    del profile_payload["STUDENT_PHOTO"]

    _assert_error_body(_authenticate(client, profile=True), 422)

    metrics = client.get("/metrics?fmt=json").json()
    assert metrics["errorsByType"] == {ProfileParseError.__name__: 1}
    assert metrics["profileParseErrors"] == {"response_structure": 1}


def test_a_validation_failure_never_reaches_pesu(client, wire):
    _assert_error_body(client.post("/authenticate", json={"username": "user"}), 400)

    assert wire.requests == []


# --- Privacy ---


def test_nothing_secret_is_logged_or_returned(client, pesu_up, secrets, caplog):
    with caplog.at_level("DEBUG"):
        response = client.post(
            "/authenticate",
            json={"username": "user", "password": "hunter2-password", "profile": True},
        )

    for secret in (*secrets, "hunter2-password"):
        assert secret not in caplog.text
        assert secret not in response.text


def test_the_upstream_error_text_is_not_forwarded(client, wire, caplog):
    """A caller learns that PESU failed, not what PESU said."""
    wire.routes[LOGIN_URL] = lambda request: httpx2.Response(500, content=b"Stack trace: internal-detail-xyz")

    body = _assert_error_body(_authenticate(client), 502)

    assert "internal-detail-xyz" not in body["message"]
