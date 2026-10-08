from unittest.mock import patch

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.app import app
from app.exceptions.authentication import AuthenticationError
from app.metrics.collector import MetricsCollector
from app.metrics.prometheus import PROMETHEUS_CONTENT_TYPE

boom_router = APIRouter()


@boom_router.get("/raiseUnhandledForMetrics", include_in_schema=False)
async def raise_unhandled():
    raise RuntimeError("Simulated internal server error")


app.include_router(boom_router)


@pytest.fixture
def client(monkeypatch):
    """A client with a *fresh* collector.

    The collector is a module-level singleton shared by the whole session, so any test asserting an
    absolute count without this is order-dependent -- and tests/conftest.py forces a fixed directory
    order, which would make such a bug look stable locally and fail elsewhere.
    """
    monkeypatch.setattr("app.app.metrics", MetricsCollector())
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def test_prometheus_endpoint_content_type(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"] == PROMETHEUS_CONTENT_TYPE


def test_prometheus_endpoint_declares_every_family(client):
    body = client.get("/metrics").text
    assert "# HELP pesu_auth_requests_total HTTP requests received.\n" in body
    assert "# TYPE pesu_auth_request_latency_seconds summary\n" in body
    assert body.endswith("\n")


def test_json_format_shape(client):
    body = client.get("/metrics?fmt=json").json()
    assert set(body) == {
        "startTimeSeconds",
        "uptimeSeconds",
        "requests",
        "requestsInFlight",
        "latency",
        "authentication",
        "authenticationResults",
        "responsesByStatus",
        "requestsByRoute",
        "errorsByType",
        "failuresByFault",
        "validationErrorsByField",
        "profileFieldFiltering",
        "profileParseErrors",
        "upstream",
        "httpClients",
        "lifespanEvents",
    }


def test_the_removed_csrf_metrics_are_gone(client):
    """The CSRF cache, refresh loop and prefetch tasks went with the web login; so did their metrics."""
    payload = client.get("/metrics?fmt=json").json()
    for key in ("csrfCache", "csrfRefreshes", "prefetchTasks"):
        assert key not in payload
    prometheus = client.get("/metrics").text
    for name in ("csrf_cache_total", "csrf_refreshes_total", "prefetch_tasks_total", "csrf_fetch"):
        assert name not in prometheus


def test_every_metric_family_appears_in_both_views(client):
    """The two views are built from one snapshot, so neither may quietly omit a family."""
    from app.metrics.collector import FAMILIES

    prometheus = client.get("/metrics").text
    for family in FAMILIES:
        assert f"# TYPE {family.name} " in prometheus, family.name


def test_a_request_is_reflected_in_both_views(client):
    client.get("/health")
    assert 'pesu_auth_route_requests_total{method="GET",route="/health"} 1' in client.get("/metrics").text
    assert "GET /health" in client.get("/metrics?fmt=json").json()["requestsByRoute"]


def test_a_successful_request_is_counted_as_success(client):
    client.get("/health")
    body = client.get("/metrics?fmt=json").json()
    assert body["responsesByStatus"]["200"] >= 1
    assert body["requests"]["failed"] == 0


@patch("app.app.pesu_academy.authenticate")
def test_an_authentication_request_records_the_profile_split(mock_authenticate, client):
    mock_authenticate.return_value = {"status": True, "message": "Login successful."}
    client.post("/authenticate", json={"username": "u", "password": "p", "profile": True})
    client.post("/authenticate", json={"username": "u", "password": "p", "profile": False})
    authentication = client.get("/metrics?fmt=json").json()["authentication"]
    assert authentication == {"total": 2, "withProfile": 1, "withoutProfile": 1}


@patch("app.app.pesu_academy.authenticate")
def test_a_failed_authentication_records_both_status_and_error_type(mock_authenticate, client):
    """The whole point of the middleware/handler split: a 401 keeps its status *and* its class."""
    mock_authenticate.side_effect = AuthenticationError()
    assert client.post("/authenticate", json={"username": "u", "password": "p"}).status_code == 401
    body = client.get("/metrics?fmt=json").json()
    assert body["responsesByStatus"]["401"] == 1
    assert body["errorsByType"]["AuthenticationError"] == 1
    assert body["requests"]["failed"] == 1


def test_a_validation_error_records_its_type(client):
    assert client.post("/authenticate", json={"password": "p"}).status_code == 400
    body = client.get("/metrics?fmt=json").json()
    assert body["responsesByStatus"]["400"] == 1
    assert body["errorsByType"]["RequestValidationError"] == 1


def test_an_unhandled_exception_records_a_500(client):
    """ServerErrorMiddleware sits above the middleware, so this path cannot be verified by reading
    the code -- only by driving a real unhandled exception through the whole stack."""
    assert client.get("/raiseUnhandledForMetrics").status_code == 500
    body = client.get("/metrics?fmt=json").json()
    assert body["responsesByStatus"]["500"] == 1
    assert body["errorsByType"]["RuntimeError"] == 1
    assert body["requests"]["failed"] == 1


def test_an_unknown_path_is_bucketed(client):
    """A 404 is counted, attributed to one bucket, and runs no handler of ours."""
    assert client.get("/definitely-not-a-route").status_code == 404
    body = client.get("/metrics?fmt=json").json()
    assert body["responsesByStatus"]["404"] == 1
    assert "GET <unmatched>" in body["requestsByRoute"]
    assert body["errorsByType"] == {}


def test_the_metrics_endpoint_counts_itself(client):
    """Scrapes are deliberately not excluded: excluding them would break the accounting invariant."""
    client.get("/metrics?fmt=json")
    assert "GET /metrics" in client.get("/metrics?fmt=json").json()["requestsByRoute"]


def test_the_default_format_is_prometheus(client):
    """A scraper hitting this path bare must get the exposition format, not JSON."""
    assert client.get("/metrics").headers["content-type"] == PROMETHEUS_CONTENT_TYPE


def test_both_formats_are_served_from_one_path(client):
    assert client.get("/metrics?fmt=prometheus").headers["content-type"] == PROMETHEUS_CONTENT_TYPE
    assert client.get("/metrics?fmt=json").headers["content-type"].startswith("application/json")


def test_an_unrecognised_format_is_rejected(client):
    """Goes through the existing validation handler, so it is a 400 and is itself counted."""
    response = client.get("/metrics?fmt=xml")
    assert response.status_code == 400
    assert "fmt" in response.json()["message"]
    assert client.get("/metrics?fmt=json").json()["errorsByType"]["RequestValidationError"] == 1


@patch("app.app.pesu_academy.authenticate")
def test_response_and_outcome_counts_agree(mock_authenticate, client):
    """sum(responsesByStatus) == success + failed, and sum(errorsByType) <= failed."""
    mock_authenticate.side_effect = AuthenticationError()
    client.get("/health")
    client.post("/authenticate", json={"username": "u", "password": "p"})
    client.get("/definitely-not-a-route")
    body = client.get("/metrics?fmt=json").json()
    resolved = body["requests"]["success"] + body["requests"]["failed"]
    assert sum(body["responsesByStatus"].values()) == resolved
    assert sum(body["errorsByType"].values()) < body["requests"]["failed"]


def test_latency_is_recorded_for_a_route(client):
    client.get("/health")
    route = client.get("/metrics?fmt=json").json()["requestsByRoute"]["GET /health"]
    assert route["latency"]["count"] == 1
    assert route["latency"]["averageSeconds"] >= 0


@patch("app.app.pesu_academy.authenticate")
def test_authentication_outcomes_are_success_or_failure(mock_authenticate, client):
    """Outcome only. Every kind of failure lands in one bucket, whatever raised it."""
    from app.exceptions.authentication import ProfileFetchError

    mock_authenticate.side_effect = AuthenticationError()
    client.post("/authenticate", json={"username": "u", "password": "p"})
    mock_authenticate.side_effect = ProfileFetchError()
    client.post("/authenticate", json={"username": "u", "password": "p", "profile": True})
    mock_authenticate.side_effect = RuntimeError("something else entirely")
    client.post("/authenticate", json={"username": "u", "password": "p"})
    mock_authenticate.side_effect = None
    mock_authenticate.return_value = {"status": True, "message": "Login successful."}
    client.post("/authenticate", json={"username": "u", "password": "p"})

    results = client.get("/metrics?fmt=json").json()["authenticationResults"]
    assert results == {"success": 1, "failure": 3}


@patch("app.app.pesu_academy.authenticate")
def test_the_reason_for_a_failure_is_still_recoverable(mock_authenticate, client):
    """Why a login failed lives in exactly one place now, named by exception class."""
    from app.exceptions.authentication import ProfileFetchError

    mock_authenticate.side_effect = AuthenticationError()
    client.post("/authenticate", json={"username": "u", "password": "p"})
    mock_authenticate.side_effect = ProfileFetchError()
    client.post("/authenticate", json={"username": "u", "password": "p", "profile": True})

    body = client.get("/metrics?fmt=json").json()
    assert body["errorsByType"] == {"AuthenticationError": 1, "ProfileFetchError": 1}
    assert body["authenticationResults"]["failure"] == 2


@patch("app.app.pesu_academy.authenticate")
def test_the_success_rate_has_a_matching_denominator(mock_authenticate, client):
    """The reason this family survives: success and failure share one denominator.

    Computing the same figure from errorsByType would mean subtracting several error classes from
    a different family, which is exactly the fragile cross-family arithmetic this avoids.
    """
    mock_authenticate.return_value = {"status": True, "message": "Login successful."}
    client.post("/authenticate", json={"username": "u", "password": "p"})
    mock_authenticate.side_effect = AuthenticationError()
    client.post("/authenticate", json={"username": "u", "password": "p"})

    body = client.get("/metrics?fmt=json").json()
    assert sum(body["authenticationResults"].values()) == body["authentication"]["total"]


def test_validation_errors_are_recorded_by_field(client):
    client.post("/authenticate", json={"password": "p"})
    client.post("/authenticate", json={"username": "u"})
    client.get("/metrics?fmt=xml")
    fields = client.get("/metrics?fmt=json").json()["validationErrorsByField"]
    assert fields == {"username": 1, "password": 1, "fmt": 1}


def test_an_unknown_field_collapses_into_one_bucket(client):
    """The body is caller-controlled, so the label set must be closed against arbitrary keys."""
    client.post("/authenticate", json={"username": "u", "password": "p", "surprise": 1})
    assert client.get("/metrics?fmt=json").json()["validationErrorsByField"] == {"other": 1}


@patch("app.app.pesu_academy.authenticate")
def test_failures_are_attributed_to_client_or_server(mock_authenticate, client):
    mock_authenticate.side_effect = AuthenticationError()
    client.post("/authenticate", json={"username": "u", "password": "p"})
    client.get("/raiseUnhandledForMetrics")
    assert client.get("/metrics?fmt=json").json()["failuresByFault"] == {"client": 1, "server": 1}


def test_in_flight_accounts_for_the_gap_in_the_totals(client):
    """total exceeds success + failed only by what is still being served -- here, this request."""
    body = client.get("/metrics?fmt=json").json()
    assert body["requestsInFlight"] == 1
    assert body["requests"]["total"] == body["requests"]["success"] + body["requests"]["failed"] + 1


def test_lifespan_startup_is_recorded(client):
    assert client.get("/metrics?fmt=json").json()["lifespanEvents"] == {"startup": 1}
