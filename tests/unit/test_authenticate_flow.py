"""/authenticate end to end: a real request through the whole app, with PESU Academy mocked on the wire.

The other unit tests check PESUAcademy and the route separately. These check what a caller actually
receives -- status code, body and headers -- for each thing PESU Academy can do, and that metrics
and logs record it.
"""

import json
from datetime import datetime

import httpx2
import pytest
from fastapi.testclient import TestClient

from app.app import app
from app.exceptions.authentication import AuthenticationError, ProfileFetchError, ProfileParseError, UpstreamError
from app.metrics.collector import MetricsCollector
from app.models import ResponseModel
from app.pesu import DISPATCHER_URL, LOGIN_URL


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


@pytest.fixture
def assert_error_body(ist_offset):
    """Check that a response is the documented error shape, with the given status, and return its body."""

    def check(response, status):
        body = response.json()
        assert response.status_code == status
        assert set(body) == {"status", "message", "timestamp"}
        assert body["status"] is False
        assert datetime.fromisoformat(body["timestamp"]).utcoffset() == ist_offset
        # The documented error shape, which callers are told to parse with ResponseModel
        ResponseModel.model_validate(body)
        return body

    return check


def test_a_login_without_a_profile(client, pesu_up, ist_offset):
    response = _authenticate(client)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"status", "message", "timestamp"}
    assert body["status"] is True
    assert body["message"] == "Login successful."
    assert datetime.fromisoformat(body["timestamp"]).utcoffset() == ist_offset
    # No profile asked for, so no profile call
    assert len(pesu_up.requests) == 1


def test_a_login_with_the_full_profile(client, pesu_up, full_profile):
    response = _authenticate(client, profile=True)

    assert response.status_code == 200
    assert response.json()["profile"] == full_profile
    assert len(pesu_up.requests) == 2


def test_a_profile_with_missing_values_returns_null(client, pesu_up, profile_payload, full_profile):
    """What a graduated student looks like on the wire: every field present, the empty ones null."""
    profile_payload["STUDENT_INFO"].update(ClassName=None, SectionName="NA")

    profile = _authenticate(client, profile=True).json()["profile"]

    assert list(profile) == list(full_profile)
    assert profile["semester"] is None
    assert profile["section"] is None


def test_requested_fields_only_and_null_when_empty(client, pesu_up, profile_payload, full_profile):
    profile_payload["STUDENT_INFO"]["ClassName"] = None

    fields = ["semester", "campusCode", "name", "middleName", "mobile", "dateOfBirth", "branchShortCode"]
    profile = _authenticate(client, profile=True, fields=fields).json()["profile"]

    assert profile == {
        "name": "JOHN DOE",
        "semester": None,
        "campusCode": 2,
        "mobile": "9876543210",
        "middleName": None,
        "branchShortCode": "CSE",
        "dateOfBirth": "2005-01-01",
    }
    # On the wire, in the documented order
    assert list(profile) == [field for field in full_profile if field in fields]


def test_fields_without_profile_return_no_profile(client, pesu_up):
    body = _authenticate(client, profile=False, fields=["name", "gender", "mobile"]).json()

    assert "profile" not in body
    assert len(pesu_up.requests) == 1


def test_the_username_is_sent_without_surrounding_whitespace(client, pesu_up):
    _authenticate(client, username="  PES2UG25CS001\n")

    assert b"PES2UG25CS001\r\n" in pesu_up.requests[0].content
    assert b"  PES2UG25CS001" not in pesu_up.requests[0].content


def test_rejected_credentials(client, wire, make_response, collector, assert_error_body):
    wire.routes[LOGIN_URL] = lambda request: make_response(401, json={"statusCode": 401})

    body = assert_error_body(_authenticate(client, profile=True), 401)

    # The documented message, not the log's detail
    assert body["message"] == "Invalid username or password, or user does not exist."
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
def test_a_login_pesu_cannot_complete_is_a_502(client, wire, collector, reply, assert_error_body):
    wire.routes[LOGIN_URL] = reply

    assert_error_body(_authenticate(client), 502)

    assert client.get("/metrics?fmt=json").json()["errorsByType"] == {UpstreamError.__name__: 1}


def test_a_failed_profile_call_is_a_502(client, pesu_up, collector, assert_error_body):
    pesu_up.routes[DISPATCHER_URL] = lambda request: httpx2.Response(503)

    assert_error_body(_authenticate(client, profile=True), 502)

    metrics = client.get("/metrics?fmt=json").json()
    assert metrics["errorsByType"] == {ProfileFetchError.__name__: 1}
    assert metrics["upstream"]["profile_fetch"]["responsesByStatus"] == {"503": 1}


def test_an_unparseable_profile_is_a_422(client, pesu_up, profile_payload, collector, assert_error_body):
    del profile_payload["STUDENT_INFO"]
    del profile_payload["STUDENT_PHOTO"]

    assert_error_body(_authenticate(client, profile=True), 422)

    metrics = client.get("/metrics?fmt=json").json()
    assert metrics["errorsByType"] == {ProfileParseError.__name__: 1}
    assert metrics["profileParseErrors"] == {"response_structure": 1}


def test_a_validation_failure_never_reaches_pesu(client, wire, assert_error_body):
    assert_error_body(client.post("/authenticate", json={"username": "user"}), 400)

    assert wire.requests == []


def test_nothing_secret_is_logged_or_returned(client, pesu_up, secrets, caplog):
    with caplog.at_level("DEBUG"):
        response = client.post(
            "/authenticate",
            json={"username": "user", "password": "hunter2-password", "profile": True},
        )

    for secret in (*secrets, "hunter2-password"):
        assert secret not in caplog.text
        assert secret not in response.text


def test_the_upstream_error_text_is_not_forwarded(client, wire, assert_error_body):
    """A caller learns that PESU failed, not what PESU said."""
    wire.routes[LOGIN_URL] = lambda request: httpx2.Response(500, content=b"Stack trace: internal-detail-xyz")

    body = assert_error_body(_authenticate(client), 502)

    assert "internal-detail-xyz" not in body["message"]


@pytest.mark.parametrize(
    ("scenario", "error", "status", "logged"),
    [
        ("rejected", AuthenticationError, 401, "user=user"),
        ("login 503", UpstreamError, 502, "with status 503"),
        ("login not json", UpstreamError, 502, "unexpected login response"),
        ("profile 503", ProfileFetchError, 502, "with status 503"),
        ("profile declined", ProfileFetchError, 502, "did not return a profile"),
        ("profile error envelope", ProfileFetchError, 502, "with error status 400"),
        ("profile unparseable", ProfileParseError, 422, "Failed to parse the profile response"),
    ],
)
def test_a_real_failure_answers_with_the_documented_message(
    client, pesu_up, profile_payload, caplog, assert_error_body, scenario, error, status, logged
):
    """The caller gets the fixed message the docs show; the specifics go only to the log.

    Driven through real PESU responses rather than a mocked authenticate, so the message is the one a
    caller actually receives.
    """
    replies = {
        "rejected": (LOGIN_URL, lambda request: httpx2.Response(401, json={"statusCode": 401})),
        "login 503": (LOGIN_URL, lambda request: httpx2.Response(503)),
        "login not json": (LOGIN_URL, lambda request: httpx2.Response(200, content=b"<html></html>")),
        "profile 503": (DISPATCHER_URL, lambda request: httpx2.Response(503)),
        "profile declined": (
            DISPATCHER_URL,
            lambda request: httpx2.Response(200, json={"MESSAGE": "FAILURE_Record not found"}),
        ),
        "profile error envelope": (
            DISPATCHER_URL,
            lambda request: httpx2.Response(200, json={"status": 400, "message": "Invalid request"}),
        ),
        "profile unparseable": (DISPATCHER_URL, lambda request: httpx2.Response(200, content=b"<html></html>")),
    }
    url, reply = replies[scenario]
    pesu_up.routes[url] = reply

    with caplog.at_level("WARNING"):
        body = assert_error_body(_authenticate(client, profile=True), status)

    assert body["message"] == error().message
    assert "user=" not in body["message"]
    # Still traceable in the log, which names the user and says what PESU answered
    record = next(r for r in caplog.records if r.getMessage().startswith(f"{error.__name__}: "))
    assert "user=user" in record.getMessage()
    assert logged in record.getMessage()


def test_personal_details_are_in_the_default_profile(client, pesu_up):
    default = _authenticate(client, profile=True).json()["profile"]
    requested = _authenticate(client, profile=True, fields=["srn", "gender", "dateOfBirth"]).json()

    assert (default["gender"], default["dateOfBirth"]) == ("Male", "2005-01-01")
    assert requested["profile"] == {"srn": "PES2UG25CS001", "gender": "Male", "dateOfBirth": "2005-01-01"}


def test_personal_details_are_null_when_pesu_has_none(client, pesu_up, profile_payload, login_payload):
    profile_payload["STUDENT_INFO"]["DateOfBirth"] = None
    profile_payload["STUDENT_PHOTO"].update(gender="", dateOfBirth=None)
    login_payload["mobileJsonObject"]["dateofBirth"] = None

    profile = _authenticate(client, profile=True, fields=["gender", "dateOfBirth"]).json()["profile"]

    assert profile == {"gender": None, "dateOfBirth": None}


def test_an_unknown_field_name_is_still_rejected(client, pesu_up, assert_error_body):
    body = assert_error_body(_authenticate(client, profile=True, fields=["fatherName"]), 400)

    assert "fields.0" in body["message"]
    assert pesu_up.requests == []


def test_blood_group_cannot_be_requested(client, pesu_up, assert_error_body):
    body = assert_error_body(_authenticate(client, profile=True, fields=["bloodGroup"]), 400)

    assert "fields.0" in body["message"]
    assert pesu_up.requests == []


@pytest.mark.parametrize("field", ["username", "password"])
def test_text_that_cannot_be_encoded_is_a_400(client, wire, caplog, field, assert_error_body):
    """An unpaired surrogate decodes from JSON but cannot be sent on; it is the caller's error, not a 500."""
    body = {"username": "user", "password": "pass"}
    raw = json.dumps(body).replace(f'"{body[field]}"', '"\\ud800abc"').encode()

    with caplog.at_level("WARNING"):
        response = client.post("/authenticate", content=raw, headers={"content-type": "application/json"})

    result = assert_error_body(response, 400)
    assert f"{field.capitalize()} contains characters that are not valid text" in result["message"]
    assert wire.requests == []
    assert not [r for r in caplog.records if r.levelname == "ERROR"]
