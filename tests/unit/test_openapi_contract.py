"""Every response the API gives must be one its OpenAPI schema documents, whatever it is sent.

test_openapi_docs.py checks that the docs exist and that their examples are valid. These tests
check the other direction: that what the routes actually answer matches those docs. Schemathesis
generates requests from the schema, valid and invalid, sends them to the real app in process, and
checks the status, Content-Type and body of each response. PESU Academy is mocked on the wire, so
each login runs the real PESUAcademy, offline; the tests below the generated ones cover the
responses generation cannot reach, and the pages the schema does not describe.
"""

import json

import httpx2
import pytest
import schemathesis
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from schemathesis.checks import not_a_server_error
from schemathesis.core.failures import FailureGroup
from schemathesis.python.asgi import ASGIClient, shutdown_lifespans

from fastapi.testclient import TestClient

from app.app import app
from app.metrics.collector import MetricsCollector
from app.models.upstream import StudentInfo, StudentPhoto
from app.pesu import DISPATCHER_URL, LOGIN_URL, PESUAcademy

# Anything PESU Academy could put in a profile field instead of the value expected there
JSON_SCALARS = st.none() | st.booleans() | st.integers() | st.floats(allow_nan=False, allow_infinity=False) | st.text()
ANY_JSON_VALUE = JSON_SCALARS | st.lists(JSON_SCALARS, max_size=2) | st.dictionaries(st.text(max_size=5), JSON_SCALARS, max_size=2)
# Stand for a field holding the value PESU Academy usually sends, and for one it leaves out altogether
KEEP, ABSENT = object(), object()
# For each block the profile is built from, what each field it reads holds in a generated response
PROFILE_BLOCKS = {
    model.BLOCK: st.fixed_dictionaries(
        {
            field.alias or name: st.just(KEEP) | ANY_JSON_VALUE | st.just(ABSENT)
            for name, field in model.model_fields.items()
        }
    )
    for model in (StudentInfo, StudentPhoto)
}
METHODS = ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")
# For the tests Schemathesis does not seed: derandomized, so they too send the same data on every run.
# Their fixtures are set up once for all their examples, which is safe because each example sets
# whatever fixture state it relies on before it sends anything.
UNSEEDED = {"derandomize": True, "suppress_health_check": [HealthCheck.function_scoped_fixture]}


@pytest.fixture
def api_schema(monkeypatch, wire, make_response, login_payload, profile_payload):
    """The app's schema, loaded in process, with PESU Academy accepting every login on the wire."""
    wire.routes[LOGIN_URL] = lambda request: make_response(json=login_payload)
    wire.routes[DISPATCHER_URL] = lambda request: make_response(json=profile_payload)
    collector = MetricsCollector()
    monkeypatch.setattr("app.app.metrics", collector)
    monkeypatch.setattr("app.app.pesu_academy._metrics", collector)
    # Seeded and without Hypothesis' example database, so every run sends the same requests
    config = schemathesis.Config.from_dict({"seed": 218, "generation": {"mode": "all", "database": "none"}})
    try:
        yield schemathesis.openapi.from_asgi("/openapi.json", app, config=config)
    finally:
        # Schemathesis keeps the app's lifespan running until the process exits; end it here,
        # while the fakes above are still in place
        shutdown_lifespans()


schema = schemathesis.pytest.from_fixture("api_schema")


def _profile_response(data, profile_payload):
    """Draw a profile response whose every field the profile reads holds its usual value, anything else, or nothing."""
    response = dict(profile_payload)
    for block, strategy in PROFILE_BLOCKS.items():
        sent = dict(profile_payload[block])
        for key, value in data.draw(strategy, label=block).items():
            if value is ABSENT:
                sent.pop(key, None)
            elif value is not KEEP:
                sent[key] = value
        response[block] = sent
    return response


@schema.include(path=["/health", "/readme"]).parametrize()
@settings(max_examples=200, database=None, deadline=None)
def test_every_generated_request_gets_a_documented_response(case, conformance_checks):
    # Redirects are not followed: /readme's 308 is the response under test, and following it would
    # leave the machine
    case.call_and_validate(checks=[not_a_server_error, *conformance_checks], allow_redirects=False)


# /authenticate is what callers use this service for, so it gets the most requests
@schema.include(path="/authenticate").parametrize()
@settings(max_examples=500, database=None, deadline=None)
def test_every_generated_authentication_request_gets_a_documented_response(
    case, wire, multipart_fields, conformance_checks
):
    """Generated requests, each logging in through the real PESUAcademy."""
    wire.requests.clear()

    response = case.call_and_validate(checks=[not_a_server_error, *conformance_checks])

    if response.status_code in (400, 405):
        # A request the API turns away never reaches PESU Academy
        assert not wire.requests
    elif response.status_code == 200:
        # The credentials reach PESU Academy as they were sent, whatever characters they hold
        fields = multipart_fields(wire.requests[0])
        assert fields["userName"] == case.body["username"].strip()
        assert fields["password"] == case.body["password"]


@given(data=st.data())
@settings(max_examples=500, database=None, deadline=None, **UNSEEDED)
def test_every_generated_profile_gets_a_documented_response(data, api_schema, wire, profile_payload, conformance_checks):
    """Generated profile responses from PESU Academy, each asked for with a generated choice of fields."""
    profile_response = _profile_response(data, profile_payload)
    wire.routes[DISPATCHER_URL] = lambda request: httpx2.Response(200, json=profile_response)
    fields = data.draw(st.none() | st.lists(st.sampled_from(PESUAcademy.DEFAULT_FIELDS), min_size=1), label="fields")
    body = {"username": "u", "password": "p", "profile": True} | ({} if fields is None else {"fields": fields})

    with ASGIClient(app) as client:
        response = client.post("/authenticate", json=body)

    api_schema["/authenticate"]["POST"].Case(body=body).validate_response(response, checks=conformance_checks)
    # A profile with nothing in STUDENT_INFO is a 422; any other is returned, with a null for each unusable value
    assert response.status_code in (200, 422)
    if response.status_code == 200:
        assert set(response.json()["profile"]) == set(fields or PESUAcademy.DEFAULT_FIELDS)


@schema.include(path="/metrics").parametrize()
@settings(max_examples=125, database=None, deadline=None)
def test_every_generated_metrics_request_gets_a_documented_response(case, monkeypatch, conformance_checks):
    monkeypatch.setattr("app.metrics.auth.METRICS_TOKEN", None)

    case.call_and_validate(checks=[not_a_server_error, *conformance_checks])


@schema.include(path="/metrics").parametrize()
@settings(max_examples=125, database=None, deadline=None)
def test_every_generated_request_for_protected_metrics_gets_a_documented_response(
    case, monkeypatch, metrics_token, conformance_checks
):
    monkeypatch.setattr("app.metrics.auth.METRICS_TOKEN", metrics_token)

    response = case.call_and_validate(checks=[not_a_server_error, *conformance_checks])

    if case.method == "GET":
        # A generated credential is never the configured token: whatever else the request gets wrong, no metrics
        assert response.status_code == 401


@pytest.fixture
def page_client():
    with TestClient(app, follow_redirects=False) as client:
        yield client


@given(data=st.data())
@settings(max_examples=200, database=None, deadline=None, **UNSEEDED)
def test_a_page_answers_any_query_and_method_as_documented(data, page, page_client, api_schema, conformance_checks):
    """The routes that take no input, sent input anyway: any query string, under any method."""
    path, status = page
    method = data.draw(st.sampled_from(METHODS), label="method")
    query = data.draw(st.dictionaries(st.text(), st.text(), max_size=3), label="query")
    # getattr: other tests mount routers of their own on the app, and those have no path
    (route,) = [route for route in app.routes if getattr(route, "path", None) == path]

    response = page_client.request(method, path, params=query)

    if method in route.methods:
        assert response.status_code == status
        if route.include_in_schema:
            api_schema[path]["GET"].Case().validate_response(response, checks=conformance_checks)
    else:
        assert response.status_code == 405
        assert set(response.headers["allow"].split(", ")) == route.methods


def test_each_authentication_failure_is_documented(api_schema, wire, conformance_checks, authentication_failure):
    url, reply, status = authentication_failure
    wire.routes[url] = reply
    case = api_schema["/authenticate"]["POST"].Case()
    # A TestClient rather than case.call(): the server re-raises an unhandled exception after rendering
    # its 500, and only a TestClient can be told to return the response instead
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/authenticate", json={"username": "u", "password": "p", "profile": True})

    case.validate_response(response, checks=conformance_checks)
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
