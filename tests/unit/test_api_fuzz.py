"""Offline contract fuzzing against the schema served by the real ASGI application."""

import os
import json
from importlib import import_module

import pytest
import schemathesis
from hypothesis import settings
from schemathesis.specs.openapi.checks import (
    content_type_conformance,
    response_schema_conformance,
    status_code_conformance,
)
from schemathesis.checks import not_a_server_error
from schemathesis.python.asgi import ASGIClient, shutdown_lifespans
from schemathesis.core.failures import FailureGroup

from scripts.fuzz.target import SYNTHETIC_TOKEN, SYNTHETIC_USERNAME, mocked_app

CHECKS = [not_a_server_error, status_code_conformance, content_type_conformance, response_schema_conformance]
MAX_EXAMPLES = int(os.environ.get("PESU_AUTH_FUZZ_EXAMPLES", "200"))


@pytest.fixture
def api_schema():
    # Load lazily: from_asgi starts the lifespan, so all backend patches must already be active.
    config = schemathesis.Config.from_dict(
        {
            "seed": 218,
            "cache": {"enabled": False},
            "generation": {"mode": "all", "database": "none"},
        }
    )
    with mocked_app(token=None) as application:
        try:
            yield schemathesis.openapi.from_asgi("/openapi.json", application, config=config)
        finally:
            # Schemathesis keeps ASGI lifespans alive until process exit by default. Close ours
            # before restoring the backend, otherwise shutdown could use the real PESU client.
            shutdown_lifespans()


schema = schemathesis.pytest.from_fixture("api_schema")


@schema.parametrize()
@settings(max_examples=MAX_EXAMPLES, database=None, deadline=None)
def test_api(case):
    case.call_and_validate(checks=CHECKS, allow_redirects=False)


@pytest.mark.parametrize(
    "payload,expected",
    [
        ({"username": SYNTHETIC_USERNAME, "password": "synthetic"}, 200),
        ({"username": SYNTHETIC_USERNAME, "password": "synthetic", "profile": True}, 200),
        (
            {
                "username": SYNTHETIC_USERNAME,
                "password": "synthetic",
                "profile": True,
                "fields": ["name", "campusCode"],
            },
            200,
        ),
        ({"username": "unknown", "password": "synthetic"}, 401),
        ({"username": "\u2603", "password": "synthetic"}, 401),
        ({"username": "u" * 4096, "password": "p" * 4096}, 401),
        ({"username": "", "password": "synthetic"}, 400),
        ({"username": SYNTHETIC_USERNAME, "password": "synthetic", "fields": []}, 400),
        ({"username": SYNTHETIC_USERNAME, "password": "synthetic", "profile": "yes"}, 400),
        ({"username": SYNTHETIC_USERNAME, "password": "synthetic", "unexpected": True}, 400),
        ({"username": SYNTHETIC_USERNAME}, 400),
        ([], 400),
    ],
)
def test_authentication_examples_match_the_contract(api_schema, payload, expected):
    case = api_schema["/authenticate"]["POST"].Case(body=payload, media_type="application/json")
    response = case.call_and_validate(checks=CHECKS, allow_redirects=False)
    assert response.status_code == expected
    body = response.json()
    assert body["status"] is (expected == 200)
    if expected != 200:
        assert set(body) == {"status", "message", "timestamp"}
    elif not payload.get("profile"):
        assert "profile" not in body
    elif payload.get("fields"):
        assert set(body["profile"]) == {"name", "campusCode"}
    else:
        assert body["profile"]["name"] == "Fuzz Student"


@pytest.mark.parametrize("fmt,expected", [("json", 200), ("prometheus", 200), ("xml", 400), ("", 400), ("\u2603", 400)])
def test_metrics_formats_match_the_contract(api_schema, fmt, expected):
    case = api_schema["/metrics"]["GET"].Case(query={"fmt": fmt})
    response = case.call_and_validate(checks=CHECKS, allow_redirects=False)
    assert response.status_code == expected


@pytest.mark.parametrize(
    "header,expected",
    [
        (None, 401),
        ("", 401),
        ("Basic synthetic", 401),
        ("Bearer", 401),
        ("Bearer wrong-token", 401),
        ("Bearer \u00fc", 401),
        (f"Bearer {SYNTHETIC_TOKEN}", 200),
    ],
)
def test_protected_metrics_match_the_contract(api_schema, monkeypatch, header, expected):
    monkeypatch.setattr("app.metrics.auth.METRICS_TOKEN", SYNTHETIC_TOKEN)
    headers = {} if header is None else {"Authorization": header}
    case = api_schema["/metrics"]["GET"].Case(query={"fmt": "json"}, headers=headers)
    response = case.call_and_validate(checks=CHECKS, allow_redirects=False)
    assert response.status_code == expected
    if expected == 401:
        assert set(response.json()) == {"status", "message", "timestamp"}
        assert response.headers["www-authenticate"] == ["Bearer"]


@pytest.mark.parametrize(
    "body,content_type",
    [
        (b"{", "application/json"),
        (b"\xff", "application/json"),
        (b"invalid", "text/plain"),
        (b"username=u", "application/x-www-form-urlencoded"),
    ],
)
def test_malformed_bodies_match_the_contract(api_schema, body, content_type):
    case = api_schema["/authenticate"]["POST"].Case()
    with ASGIClient(api_schema.app) as client:
        response = client.post("/authenticate", data=body, headers={"Content-Type": content_type})
    case.validate_response(response, checks=CHECKS)
    assert response.status_code == 400


def test_mocked_target_restores_state_and_closes_lifespan():
    app_module = import_module("app.app")
    original = (app_module.metrics, app_module.pesu_academy, app_module.app.openapi_schema)
    with mocked_app() as application:
        backend = app_module.pesu_academy
        try:
            schemathesis.openapi.from_asgi("/openapi.json", application)
        finally:
            shutdown_lifespans()
        backend.prefetch_client_with_csrf_token.assert_awaited_once()
        backend.close_client.assert_awaited_once()
    assert (app_module.metrics, app_module.pesu_academy, app_module.app.openapi_schema) == original


def test_unreadable_json_is_counted_without_exposing_the_body(api_schema, caplog):
    from app.metrics.collector import ERRORS_BY_TYPE, VALIDATION_ERRORS

    app_module = import_module("app.app")
    sentinel = b"synthetic-private-value"
    with ASGIClient(api_schema.app) as client, caplog.at_level("WARNING"):
        response = client.post("/authenticate", data=b"\xff" + sentinel, headers={"Content-Type": "application/json"})
    assert response.status_code == 400
    assert set(response.json()) == {"status", "message", "timestamp"}
    assert response.json()["message"] == "Could not parse request body."
    assert sentinel.decode() not in caplog.text
    assert sentinel.decode() not in response.text
    snapshot = app_module.metrics.snapshot()
    assert snapshot.value(ERRORS_BY_TYPE.name, type="RequestBodyParseError") == 1
    assert snapshot.value(VALIDATION_ERRORS.name, field="body") == 0


def test_unmatched_routes_keep_the_framework_response(api_schema):
    with ASGIClient(api_schema.app) as client:
        response = client.get("/not-a-route")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


@pytest.mark.parametrize(
    "fault,title",
    [
        ("server", "Server error"),
        ("status", "Undocumented HTTP status code"),
        ("content_type", "Undocumented Content-Type"),
        ("schema", "Response violates schema"),
    ],
)
def test_contract_checks_detect_broken_responses(api_schema, fault, title):
    case = api_schema["/health"]["GET"].Case()
    response = case.call(allow_redirects=False)
    if fault == "server":
        response.status_code = 500  # Documented, but still forbidden by not_a_server_error.
    elif fault == "status":
        response.status_code = 418
    elif fault == "content_type":
        response.headers["content-type"] = ["application/xml"]
    else:
        body = response.json()
        body["status"] = "wrong-type"
        response.content = json.dumps(body).encode()
    with pytest.raises(FailureGroup) as raised:
        case.validate_response(response, checks=CHECKS)
    assert title in {failure.title for failure in raised.value.exceptions}
