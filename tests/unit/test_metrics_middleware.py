import asyncio

import pytest

from app.metrics.collector import (
    ERRORS_BY_TYPE,
    REQUEST_LATENCY,
    REQUESTS_FAILED,
    REQUESTS_IN_FLIGHT,
    REQUESTS_SUCCESS,
    REQUESTS_TOTAL,
    RESPONSES_BY_STATUS,
    ROUTE_LATENCY,
    ROUTE_REQUESTS,
    MetricsCollector,
)
from app.metrics.middleware import (
    OTHER_METHOD,
    UNMATCHED_ROUTE,
    method_label,
    record_request_metrics,
    route_label,
)


class FakeRequest:
    """Only `scope` is read by the middleware, so nothing else needs to exist."""

    def __init__(self, scope):
        self.scope = scope


class FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code


class FakeRoute:
    def __init__(self, path):
        self.path = path


def scope(method="GET", route="/health", **extra):
    s = {"method": method, **extra}
    if route is not None:
        s["route"] = FakeRoute(route)
    return s


def responding(status):
    async def call_next(_request):
        return FakeResponse(status)

    return call_next


def raising(exc):
    async def call_next(_request):
        raise exc

    return call_next


@pytest.fixture
def collector():
    return MetricsCollector(clock=lambda: 1000.0)


@pytest.mark.asyncio
async def test_a_success_is_recorded(collector):
    await record_request_metrics(collector, FakeRequest(scope()), responding(200))
    snapshot = collector.snapshot()
    assert snapshot.value(REQUESTS_TOTAL.name) == 1.0
    assert snapshot.value(REQUESTS_SUCCESS.name) == 1.0
    assert snapshot.value(REQUESTS_FAILED.name) == 0.0
    assert snapshot.value(RESPONSES_BY_STATUS.name, status="200") == 1.0
    assert snapshot.value(ROUTE_REQUESTS.name, method="GET", route="/health") == 1.0
    assert snapshot.value(f"{REQUEST_LATENCY.name}_count") == 1.0
    assert snapshot.value(f"{ROUTE_LATENCY.name}_count", method="GET", route="/health") == 1.0


@pytest.mark.asyncio
async def test_the_response_is_returned_unchanged(collector):
    response = await record_request_metrics(collector, FakeRequest(scope()), responding(200))
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_a_4xx_is_counted_as_a_failure(collector):
    await record_request_metrics(collector, FakeRequest(scope(method="POST", route="/authenticate")), responding(401))
    snapshot = collector.snapshot()
    assert snapshot.value(REQUESTS_FAILED.name) == 1.0
    assert snapshot.value(REQUESTS_SUCCESS.name) == 0.0
    assert snapshot.value(RESPONSES_BY_STATUS.name, status="401") == 1.0


@pytest.mark.asyncio
async def test_a_redirect_is_not_counted_as_a_failure(collector):
    """/readme answers 308. A `status < 300` success test would call every readme hit a failure."""
    await record_request_metrics(collector, FakeRequest(scope(route="/readme")), responding(308))
    snapshot = collector.snapshot()
    assert snapshot.value(REQUESTS_SUCCESS.name) == 1.0
    assert snapshot.value(REQUESTS_FAILED.name) == 0.0


@pytest.mark.asyncio
async def test_a_raised_exception_is_counted_and_re_raised(collector):
    """A raised exception is recorded as a 500 and re-raised.

    ServerErrorMiddleware renders the 500 above us, so we never see that response -- we must record the status
    ourselves or requests_total stops matching the sum of responses_total.
    """
    with pytest.raises(RuntimeError, match="boom"):
        await record_request_metrics(collector, FakeRequest(scope()), raising(RuntimeError("boom")))
    snapshot = collector.snapshot()
    assert snapshot.value(REQUESTS_TOTAL.name) == 1.0
    assert snapshot.value(REQUESTS_FAILED.name) == 1.0
    assert snapshot.value(RESPONSES_BY_STATUS.name, status="500") == 1.0
    assert snapshot.value(f"{REQUEST_LATENCY.name}_count") == 1.0


@pytest.mark.asyncio
async def test_an_exception_does_not_record_an_error_type(collector):
    """The no-double-count invariant: the type is the exception handlers' job, not the middleware's."""
    with pytest.raises(RuntimeError):
        await record_request_metrics(collector, FakeRequest(scope()), raising(RuntimeError("boom")))
    assert list(collector.snapshot().samples(ERRORS_BY_TYPE.name)) == []


@pytest.mark.asyncio
async def test_cancellation_is_not_recorded(collector):
    """A client disconnect surfaces as cancellation, which is not recorded.

    Swallowing it to record would be worse than the small undercount, so it propagates untouched and total
    exceeds success + failed.
    """
    with pytest.raises(asyncio.CancelledError):
        await record_request_metrics(collector, FakeRequest(scope()), raising(asyncio.CancelledError()))
    snapshot = collector.snapshot()
    assert snapshot.value(REQUESTS_TOTAL.name) == 1.0
    assert snapshot.value(REQUESTS_SUCCESS.name) == 0.0
    assert snapshot.value(REQUESTS_FAILED.name) == 0.0
    # The gauge must still come back down, or it climbs forever on a server that sees disconnects
    assert snapshot.value(REQUESTS_IN_FLIGHT.name) == 0.0


@pytest.mark.asyncio
async def test_in_flight_returns_to_zero_on_every_path(collector):
    """Success, handled failure and raised exception must all leave the gauge where they found it."""
    await record_request_metrics(collector, FakeRequest(scope()), responding(200))
    await record_request_metrics(collector, FakeRequest(scope()), responding(401))
    with pytest.raises(RuntimeError):
        await record_request_metrics(collector, FakeRequest(scope()), raising(RuntimeError("boom")))
    assert collector.snapshot().value(REQUESTS_IN_FLIGHT.name) == 0.0


@pytest.mark.asyncio
async def test_in_flight_is_raised_while_a_request_is_being_served(collector):
    async def call_next(_request):
        assert collector.snapshot().value(REQUESTS_IN_FLIGHT.name) == 1.0
        return FakeResponse(200)

    await record_request_metrics(collector, FakeRequest(scope()), call_next)
    assert collector.snapshot().value(REQUESTS_IN_FLIGHT.name) == 0.0


@pytest.mark.asyncio
async def test_latency_is_recorded_as_a_positive_duration(collector):
    await record_request_metrics(collector, FakeRequest(scope()), responding(200))
    assert collector.snapshot().value(f"{REQUEST_LATENCY.name}_sum") >= 0.0


def test_route_label_uses_the_matched_template():
    assert route_label(scope(route="/authenticate")) == "/authenticate"


def test_route_label_falls_back_for_an_unmatched_path():
    """A scanner walking arbitrary paths must land in one bucket, not mint a series per probe."""
    assert route_label({"method": "GET", "path": "/wp-login.php"}) == UNMATCHED_ROUTE


def test_route_label_uses_the_path_for_a_non_api_route():
    """Swagger UI and /openapi.json are plain Starlette routes: they set endpoint, never route."""
    assert route_label({"method": "GET", "path": "/openapi.json", "endpoint": object()}) == "/openapi.json"


def test_route_label_ignores_a_route_without_a_path():
    assert route_label({"method": "GET", "route": object()}) == UNMATCHED_ROUTE


def test_method_label_passes_known_verbs():
    for method in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"):
        assert method_label({"method": method}) == method


def test_method_label_clamps_an_unknown_verb():
    assert method_label({"method": "PROPFIND"}) == OTHER_METHOD


def test_method_label_handles_a_scope_without_a_method():
    assert method_label({}) == OTHER_METHOD
