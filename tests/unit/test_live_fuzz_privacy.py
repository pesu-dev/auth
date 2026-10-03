"""Prove live fuzz failures keep credentials and profiles out of pytest reports, offline."""

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import Mock

import httpx2
import pytest

if TYPE_CHECKING:
    from types import ModuleType

PRIVATE_USERNAME = "synthetic-private-username@example.invalid"
PRIVATE_PASSWORD = "synthetic-private-password-sentinel"
PRIVATE_PROFILE = "synthetic-private-profile-sentinel"
PRIVATE_TOKEN = "synthetic-private-token-sentinel"
PRIVATE_VALUES = (PRIVATE_USERNAME, PRIVATE_PASSWORD, PRIVATE_PROFILE, PRIVATE_TOKEN)


@pytest.fixture
def live_module(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Load the generated live test with only synthetic private values in its environment."""
    monkeypatch.setenv("TEST_EMAIL", PRIVATE_USERNAME)
    monkeypatch.setenv("TEST_PASSWORD", PRIVATE_PASSWORD)
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "integration"))
    return import_module("test_api_fuzz_live")


def _response(status: int, body: dict[str, Any]) -> httpx2.Response:
    """Fabricate a response and request containing private sentinels without any network call."""
    request = httpx2.Request(
        "POST",
        "http://testserver/authenticate",
        headers={"Authorization": f"Bearer {PRIVATE_TOKEN}"},
        json={"username": PRIVATE_USERNAME, "password": PRIVATE_PASSWORD},
    )
    response = httpx2.Response(status, json=body, request=request)
    response.elapsed = timedelta(milliseconds=1)
    return response


@pytest.mark.parametrize("failure", ["schema", "transport", "status"])
def test_live_fuzz_reports_hide_private_data_and_preserve_generated_case(live_module: ModuleType, failure: str) -> None:
    """Fail safely while supplying credentials solely at the client request boundary."""
    generated = {
        "username": "generated-username",
        "password": "generated-password",
        "profile": True,
    }
    schema = live_module.live_schema.__wrapped__()
    case = schema["/authenticate"]["POST"].Case(body=generated, media_type="application/json")
    original_body = deepcopy(case.body)
    client = Mock(spec=["post"])
    if failure == "transport":
        client.post.side_effect = RuntimeError(" ".join(PRIVATE_VALUES))
    elif failure == "schema":
        client.post.return_value = _response(200, {"status": "invalid", "profile": {"name": PRIVATE_PROFILE}})
    else:
        client.post.return_value = _response(
            401,
            {"status": False, "message": PRIVATE_PROFILE, "timestamp": "2026-10-02T00:00:00Z"},
        )

    # Schemathesis' lazy decorator retains the original test body here. Calling it directly
    # exercises the credential boundary and validation without starting the real app lifespan.
    test_body = live_module.test_authenticate_with_real_credentials._schemathesis_given_target
    with pytest.raises(pytest.fail.Exception) as error:
        test_body(case, client)

    # str(error) hides the important leak: pytest can render a chained FailureGroup containing
    # an entire real profile even when the outer failure has pytrace=False.
    representation = str(error.getrepr(style="value"))
    assert all(value not in representation for value in PRIVATE_VALUES)
    assert error.value.__suppress_context__ or error.value.__context__ is None
    assert case.body == original_body
    assert all(value not in repr(case.body) for value in PRIVATE_VALUES)
    client.post.assert_called_once_with(
        "/authenticate",
        json={**original_body, "username": PRIVATE_USERNAME, "password": PRIVATE_PASSWORD},
    )
    assert "Live Schemathesis" in representation


def test_existing_live_contract_failure_hides_profile_and_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent the ordinary real-response validator from leaking a chained profile failure."""
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "integration"))
    app_module = import_module("app.app")
    # Importing the existing integration module registers its test-only route. Preserve the
    # application's route list when this privacy module is run on its own.
    monkeypatch.setattr(app_module.app.router, "routes", list(app_module.app.router.routes))
    integration = import_module("test_app_integration")
    validator = integration.live_contract.__wrapped__()
    response = _response(200, {"status": "invalid", "profile": {"name": PRIVATE_PROFILE}})

    with pytest.raises(pytest.fail.Exception) as error:
        validator(response)

    representation = str(error.getrepr(style="value"))
    assert all(value not in representation for value in PRIVATE_VALUES)
    assert error.value.__suppress_context__
    assert "Real /authenticate response violates OpenAPI: Response violates schema" in representation
