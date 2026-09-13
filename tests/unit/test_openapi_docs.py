"""Tests that the OpenAPI schema documents what the API actually does.

Swagger is what a caller reads before writing any code against this service, so an example that
does not match reality is worse than no example. These tests check the documentation against the
models it claims to follow, and against real responses.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.app import app
from app.exceptions.authentication import AuthenticationError
from app.models import MetricsModel, RequestModel, ResponseModel

MODELS = {"ResponseModel": ResponseModel, "MetricsModel": MetricsModel}


@pytest.fixture(scope="module")
def schema():
    app.openapi_schema = None
    generated = app.openapi()
    app.openapi_schema = None
    return generated


@pytest.fixture
def client():
    with (
        patch("app.app.pesu_academy.prefetch_client_with_csrf_token", new_callable=AsyncMock),
        patch("app.app.pesu_academy.close_client", new_callable=AsyncMock),
    ):
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client


def _operations(schema):
    for path, operations in schema["paths"].items():
        for verb, operation in operations.items():
            yield path, verb, operation


def test_every_route_is_documented(schema):
    assert set(schema["paths"]) == {"/authenticate", "/health", "/metrics", "/readme"}


def test_every_route_documents_a_success_and_a_server_error(schema):
    """Any route can 500 through the catch-all handler, so every one documents it."""
    for path, verb, operation in _operations(schema):
        codes = set(operation["responses"])
        assert codes & {"200", "308"}, f"{verb} {path} documents no success"
        assert "500" in codes, f"{verb} {path} does not document a 500"


def test_every_documented_response_has_an_example(schema):
    for path, verb, operation in _operations(schema):
        for code, response in operation["responses"].items():
            for media_type, content in response.get("content", {}).items():
                has_example = "example" in content or "examples" in content
                assert has_example, f"{verb} {path} {code} {media_type} has no example"


def test_every_documented_response_has_a_schema(schema):
    for path, verb, operation in _operations(schema):
        for code, response in operation["responses"].items():
            for media_type, content in response.get("content", {}).items():
                assert "schema" in content, f"{verb} {path} {code} {media_type} has no schema"


def test_json_examples_validate_against_the_model_they_claim(schema):
    """An example its own declared model rejects would mislead every reader.

    Validated **both** ways. JSON mode is what a caller parsing a response body is in; Python mode
    is what a caller passing a decoded dict is in. A published model that only works in one of them
    is a trap, so both are asserted rather than picking whichever passes.
    """
    checked = 0
    for path, verb, operation in _operations(schema):
        for code, response in operation["responses"].items():
            content = response.get("content", {}).get("application/json", {})
            ref = content.get("schema", {}).get("$ref", "")
            model = MODELS.get(ref.rsplit("/", 1)[-1])
            if model is None or "example" not in content:
                continue
            model.model_validate_json(json.dumps(content["example"]))
            model.model_validate(content["example"])
            checked += 1
    assert checked >= 8, f"only {checked} examples were checked; the sweep is not doing its job"


def test_request_examples_validate_against_the_request_model(schema):
    body = schema["paths"]["/authenticate"]["post"]["requestBody"]["content"]["application/json"]
    examples = body["examples"]
    assert len(examples) >= 3
    for name, example in examples.items():
        RequestModel.model_validate_json(json.dumps(example["value"])), name
        RequestModel.model_validate(example["value"]), name


def test_request_examples_cover_the_documented_username_forms(schema):
    """The endpoint accepts SRN/PRN, email and phone, so the examples should show all three."""
    body = schema["paths"]["/authenticate"]["post"]["requestBody"]["content"]["application/json"]
    usernames = [e["value"]["username"] for e in body["examples"].values()]
    assert any("@" in u for u in usernames), "no email example"
    assert any(u.isdigit() for u in usernames), "no phone example"
    assert any(u.startswith("PES") for u in usernames), "no SRN/PRN example"


def test_request_examples_cover_profile_and_field_filtering(schema):
    body = schema["paths"]["/authenticate"]["post"]["requestBody"]["content"]["application/json"]
    values = [e["value"] for e in body["examples"].values()]
    assert any(v.get("profile") is False for v in values), "no example without profile"
    assert any(v.get("profile") is True for v in values), "no example with profile"
    assert any("fields" in v for v in values), "no example using field filtering"


def test_no_phantom_validation_error_is_documented(schema):
    """This API converts every RequestValidationError into a 400.

    FastAPI would otherwise document a 422 carrying its own HTTPValidationError body on any route
    with validatable parameters -- a response that cannot occur, in a shape never emitted.
    """
    assert "HTTPValidationError" not in schema["components"]["schemas"]
    assert "422" not in schema["paths"]["/metrics"]["get"]["responses"]
    rendered = str(schema)
    assert "HTTPValidationError" not in rendered


def test_the_profile_parse_422_is_kept(schema):
    """/authenticate really can return a 422, and it uses this API's own response shape."""
    response = schema["paths"]["/authenticate"]["post"]["responses"]["422"]
    ref = response["content"]["application/json"]["schema"]["$ref"]
    assert ref.endswith("/ResponseModel")


def test_the_metrics_format_enum_is_documented(schema):
    values = schema["components"]["schemas"]["MetricsFormat"]["enum"]
    assert sorted(values) == ["json", "prometheus"]


def test_the_metrics_token_scheme_is_documented(schema):
    """Swagger's Authorize button is how a reader discovers the endpoint can be protected."""
    scheme = schema["components"]["securitySchemes"]["MetricsToken"]
    assert scheme["type"] == "http"
    assert scheme["scheme"] == "bearer"
    assert "METRICS_TOKEN" in scheme["description"]


def test_only_metrics_requires_the_token(schema):
    """/health must stay open: Render's own health check and the uptime monitors send no token."""
    secured = {path for path, _, operation in _operations(schema) if operation.get("security")}
    assert secured == {"/metrics"}
    assert schema["paths"]["/metrics"]["get"]["security"] == [{"MetricsToken": []}]


def test_the_documented_metrics_401_matches_a_real_response(client, schema, monkeypatch):
    """The 401 body a scraper gets must be the one Swagger shows."""
    documented = schema["paths"]["/metrics"]["get"]["responses"]["401"]["content"]["application/json"]["example"]
    monkeypatch.setattr("app.metrics.auth.METRICS_TOKEN", "some-token")
    response = client.get("/metrics")
    assert response.status_code == 401
    assert response.json()["message"] == documented["message"]
    assert set(response.json()) == set(documented)


def test_the_documented_400_matches_a_real_response(client, schema):
    """The example a reader copies must be the body they will actually receive."""
    documented = schema["paths"]["/metrics"]["get"]["responses"]["400"]["content"]["application/json"]["example"]
    actual = client.get("/metrics?fmt=xml").json()
    assert actual["status"] == documented["status"]
    assert actual["message"] == documented["message"]
    assert set(actual) == set(documented)


@patch("app.app.pesu_academy.authenticate")
def test_the_documented_401_matches_a_real_response(mock_authenticate, client, schema):
    mock_authenticate.side_effect = AuthenticationError()
    documented = schema["paths"]["/authenticate"]["post"]["responses"]["401"]["content"]["application/json"]["example"]
    actual = client.post("/authenticate", json={"username": "u", "password": "p"}).json()
    assert set(actual) == set(documented)
    assert actual["status"] == documented["status"] is False


def test_the_documented_health_200_matches_a_real_response(client, schema):
    documented = schema["paths"]["/health"]["get"]["responses"]["200"]["content"]["application/json"]["example"]
    actual = client.get("/health").json()
    assert set(actual) == set(documented)
    assert actual["message"] == documented["message"]


def test_the_documented_prometheus_example_looks_like_the_real_payload(client, schema):
    documented = schema["paths"]["/metrics"]["get"]["responses"]["200"]["content"]["text/plain"]["example"]
    actual = client.get("/metrics").text
    for line in documented.splitlines():
        if line.startswith("# TYPE"):
            assert line in actual, f"documented family missing from a real response: {line}"


def test_every_route_is_tagged(schema):
    for path, verb, operation in _operations(schema):
        assert operation.get("tags"), f"{verb} {path} has no tag"


def test_every_route_has_a_summary_and_description(schema):
    """The summary is the line Swagger shows collapsed; without it a reader sees only the path."""
    for path, verb, operation in _operations(schema):
        assert operation.get("summary"), f"{verb} {path} has no summary"
        assert operation.get("description"), f"{verb} {path} has no description"


def test_the_schema_is_built_once_and_cached():
    """FastAPI caches the schema on the app; the override must keep doing so, not rebuild per request."""
    app.openapi_schema = None
    first = app.openapi()
    second = app.openapi()
    assert first is second
    app.openapi_schema = None


def test_a_real_response_can_be_parsed_with_the_published_model(client):
    """The published schema has to be usable by a client, which is the point of publishing it.

    A real response carries `timestamp` as an ISO string. If the model could only be validated in
    JSON mode, anyone holding a decoded dict -- which is what every HTTP library hands back -- would
    be unable to use it.
    """
    body = client.get("/health").json()
    assert ResponseModel.model_validate(body).status is True
    assert ResponseModel.model_validate_json(json.dumps(body)).status is True


def test_the_model_still_rejects_a_wrong_type_elsewhere(client):
    """Relaxing `timestamp` must not have relaxed the model as a whole."""
    body = client.get("/health").json()
    with pytest.raises(Exception, match="status"):
        ResponseModel.model_validate({**body, "status": "not-a-bool"})
