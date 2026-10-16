"""Every response the API gives must be one its OpenAPI schema documents.

test_openapi_docs.py checks that the docs exist and that their examples are valid. These tests
check the other direction: that what the routes actually answer matches those docs. Schemathesis
generates requests from the schema, valid and invalid, sends them to the real app in process, and
checks the status, Content-Type and body of each response. PESU Academy is mocked, so this runs
offline; the tests below the generated one cover the responses generation cannot reach.
"""

import json
from unittest.mock import AsyncMock

import pytest
import schemathesis
from hypothesis import settings
from schemathesis.checks import not_a_server_error
from schemathesis.core.failures import FailureGroup
from schemathesis.python.asgi import ASGIClient, shutdown_lifespans

from app.app import app
from app.metrics.collector import MetricsCollector


@pytest.fixture
def api_schema(monkeypatch, full_profile):
    """The app's schema, loaded in process, with every login succeeding against a fake PESU Academy."""

    async def authenticate(username, password, profile=False, fields=None):
        result = {"status": True, "message": "Login successful."}
        if profile:
            result["profile"] = {field: value for field, value in full_profile.items() if fields is None or field in fields}
        return result

    monkeypatch.setattr("app.app.pesu_academy.authenticate", authenticate)
    monkeypatch.setattr("app.app.metrics", MetricsCollector())
    # Seeded and without Hypothesis' example database, so every run sends the same requests
    config = schemathesis.Config.from_dict({"seed": 218, "generation": {"mode": "all", "database": "none"}})
    try:
        yield schemathesis.openapi.from_asgi("/openapi.json", app, config=config)
    finally:
        # Schemathesis keeps the app's lifespan running until the process exits; end it here,
        # while the fakes above are still in place
        shutdown_lifespans()


schema = schemathesis.pytest.from_fixture("api_schema")


@schema.parametrize()
@settings(max_examples=100, database=None, deadline=None)
def test_every_generated_request_gets_a_documented_response(case, conformance_checks):
    # Redirects are not followed: /readme's 308 is the response under test, and following it would
    # leave the machine
    case.call_and_validate(checks=[not_a_server_error, *conformance_checks], allow_redirects=False)


def test_each_authentication_failure_is_documented(api_schema, conformance_checks, authentication_failure, monkeypatch):
    error, status = authentication_failure
    monkeypatch.setattr("app.app.pesu_academy.authenticate", AsyncMock(side_effect=error))
    case = api_schema["/authenticate"]["POST"].Case(body={"username": "u", "password": "p"}, media_type="application/json")

    response = case.call_and_validate(checks=conformance_checks)

    assert response.status_code == status


def test_an_unreadable_body_gets_a_documented_response(api_schema, conformance_checks, unreadable_body):
    """Bodies Schemathesis cannot build from the schema, sent as raw bytes."""
    content, content_type = unreadable_body
    case = api_schema["/authenticate"]["POST"].Case()
    with ASGIClient(app) as client:
        response = client.post("/authenticate", data=content, headers={"Content-Type": content_type})

    case.validate_response(response, checks=conformance_checks)
    assert response.status_code == 400


@pytest.mark.parametrize("header", [None, "Bearer wrong-token", "Basic dXNlcg==", "Bearer ü"])
def test_a_rejected_metrics_token_gets_a_documented_response(api_schema, conformance_checks, metrics_token, monkeypatch, header):
    monkeypatch.setattr("app.metrics.auth.METRICS_TOKEN", metrics_token)
    headers = {} if header is None else {"Authorization": header}
    case = api_schema["/metrics"]["GET"].Case(query={"fmt": "json"}, headers=headers)

    response = case.call_and_validate(checks=conformance_checks)

    assert response.status_code == 401


@pytest.mark.parametrize("fmt", ["json", "prometheus"])
def test_an_accepted_metrics_token_gets_a_documented_response(api_schema, conformance_checks, metrics_token, monkeypatch, fmt):
    monkeypatch.setattr("app.metrics.auth.METRICS_TOKEN", metrics_token)
    case = api_schema["/metrics"]["GET"].Case(query={"fmt": fmt}, headers={"Authorization": f"Bearer {metrics_token}"})

    response = case.call_and_validate(checks=conformance_checks)

    assert response.status_code == 200


@pytest.mark.parametrize(
    "fault, title",
    [
        ("status", "Undocumented HTTP status code"),
        ("content_type", "Undocumented Content-Type"),
        ("body", "Response violates schema"),
    ],
)
def test_the_checks_reject_a_response_that_breaks_the_schema(api_schema, conformance_checks, fault, title):
    """Without this, a check that silently passed everything would make every test above pass too."""
    case = api_schema["/health"]["GET"].Case()
    response = case.call()
    if fault == "status":
        response.status_code = 418
    elif fault == "content_type":
        response.headers["content-type"] = ["application/xml"]
    else:
        # From the bytes, not response.json(): that caches the body, and the check would read the cache
        response.content = json.dumps({**json.loads(response.content), "status": "not a boolean"}).encode()

    with pytest.raises(FailureGroup) as exc_info:
        case.validate_response(response, checks=conformance_checks)

    assert title in {failure.title for failure in exc_info.value.exceptions}
