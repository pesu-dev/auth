"""Schemathesis-generated authentication requests using the real .env account."""

import os

import pytest
import schemathesis
from fastapi.testclient import TestClient
from hypothesis import Phase, settings
from pydantic import ValidationError
from schemathesis.checks import not_a_server_error
from schemathesis.core.failures import FailureGroup
from schemathesis.specs.openapi.checks import (
    content_type_conformance,
    response_schema_conformance,
    status_code_conformance,
)

from app.app import app
from app.models import RequestModel


@pytest.fixture
def live_schema():
    # tests/conftest.py loads .env before collection, just like the other live tests.
    if not os.getenv("TEST_EMAIL") or not os.getenv("TEST_PASSWORD"):
        pytest.skip("Live Schemathesis tests require TEST_EMAIL and TEST_PASSWORD in .env.")
    config = schemathesis.Config.from_dict(
        {
            "seed": 218,
            "cache": {"enabled": False},
            "generation": {"mode": "positive", "database": "none"},
            "phases": {"enabled": False, "fuzzing": {"enabled": True}},
            "output": {"sanitization": {"enabled": True}},
        }
    )
    return schemathesis.openapi.from_dict(app.openapi(), config=config)


@pytest.fixture
def live_client(live_schema):
    # This lifespan and every authentication call use the real PESU backend. Requests are serial.
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


schema = schemathesis.pytest.from_fixture("live_schema").include(path="/authenticate")


@pytest.mark.secret_required
@schema.parametrize()
@settings(max_examples=6, database=None, deadline=None, phases=[Phase.generate])
def test_authenticate_with_real_credentials(case, live_client):
    # Generate profile/fields combinations from OpenAPI, but supply the actual credentials only
    # at the HTTP boundary. Never put them in Case: Hypothesis may print or replay generated cases.
    payload = {
        **case.body,
        "username": os.environ["TEST_EMAIL"],
        "password": os.environ["TEST_PASSWORD"],
    }
    try:
        RequestModel.model_validate(payload)
    except ValidationError:
        expected_status = 400
    else:
        expected_status = 200
    # Use an empty case for validation so even error reproductions cannot contain real credentials.
    validation_schema = schemathesis.openapi.from_dict(app.openapi(), config=schemathesis.Config())
    validation_schema.config.output.sanitization.update(enabled=True)
    validation_case = validation_schema["/authenticate"]["POST"].Case()
    try:
        response = live_client.post("/authenticate", json=payload)
        validation_case.validate_response(
            response,
            checks=[
                not_a_server_error,
                status_code_conformance,
                content_type_conformance,
                response_schema_conformance,
            ],
        )
    except FailureGroup as failures:
        titles = ", ".join(sorted({failure.title for failure in failures.exceptions}))
        raise pytest.fail.Exception(f"Live Schemathesis response violates OpenAPI: {titles}", pytrace=False) from None
    except Exception:
        # HTTP/schema errors can retain bodies or request objects; print no exception details.
        raise pytest.fail.Exception("Live Schemathesis request or validation failed.", pytrace=False) from None
    if response.status_code != expected_status:
        pytest.fail(
            f"Live Schemathesis expected status {expected_status}, received {response.status_code}.",
            pytrace=False,
        )
