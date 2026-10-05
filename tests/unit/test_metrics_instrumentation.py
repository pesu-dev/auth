"""Tests that the instrumentation records what it claims, path by path."""

import asyncio
from unittest.mock import AsyncMock

import httpx2
import pytest

from app.exceptions.authentication import AuthenticationError, ProfileFetchError, UpstreamError
from app.metrics.collector import (
    HTTP_CLIENTS,
    PROFILE_FIELD_FILTERING,
    UPSTREAM_LATENCY,
    UPSTREAM_REQUESTS,
    UPSTREAM_RESPONSES,
    MetricsCollector,
)
from app.pesu import PESUAcademy, _close_client_quietly


@pytest.fixture
def collector():
    return MetricsCollector(clock=lambda: 1000.0)


@pytest.fixture
def pesu(collector):
    return PESUAcademy(collector)


@pytest.mark.asyncio
async def test_a_login_records_its_upstream_call(pesu, collector, upstream, make_response, login_payload):
    upstream.side_effect = [make_response(json=login_payload)]

    await pesu.authenticate("u", "p")

    snapshot = collector.snapshot()
    assert snapshot.value(UPSTREAM_REQUESTS.name, operation="login", outcome="success") == 1.0
    assert snapshot.value(UPSTREAM_RESPONSES.name, operation="login", status="200") == 1.0
    assert snapshot.value(f"{UPSTREAM_LATENCY.name}_count", operation="login") == 1.0
    # No profile was asked for, so the dispatcher was never called
    assert snapshot.value(f"{UPSTREAM_LATENCY.name}_count", operation="profile_fetch") == 0.0
    # The client this request created is closed on the way out
    assert snapshot.value(HTTP_CLIENTS.name, event="created") == 1.0
    assert snapshot.value(HTTP_CLIENTS.name, event="closed") == 1.0


@pytest.mark.asyncio
async def test_a_profile_fetch_records_its_upstream_call(
    pesu, collector, upstream, make_response, login_payload, profile_payload
):
    upstream.side_effect = [make_response(json=login_payload), make_response(json=profile_payload)]

    await pesu.authenticate("u", "p", profile=True)

    snapshot = collector.snapshot()
    assert snapshot.value(UPSTREAM_REQUESTS.name, operation="profile_fetch", outcome="success") == 1.0
    assert snapshot.value(UPSTREAM_RESPONSES.name, operation="profile_fetch", status="200") == 1.0
    assert snapshot.value(f"{UPSTREAM_LATENCY.name}_count", operation="profile_fetch") == 1.0


@pytest.mark.asyncio
async def test_a_wrong_password_still_counts_the_login_as_reaching_pesu(pesu, collector, upstream, make_response):
    """PESU answered, with a 401. The call worked; the credentials did not."""
    upstream.side_effect = [make_response(401, json={"statusCode": 401})]

    with pytest.raises(AuthenticationError):
        await pesu.authenticate("u", "wrong")

    snapshot = collector.snapshot()
    assert snapshot.value(UPSTREAM_REQUESTS.name, operation="login", outcome="success") == 1.0
    assert snapshot.value(UPSTREAM_REQUESTS.name, operation="login", outcome="error") == 0.0
    assert snapshot.value(UPSTREAM_RESPONSES.name, operation="login", status="401") == 1.0


@pytest.mark.asyncio
async def test_a_failing_login_is_recorded_as_an_error(pesu, collector, upstream):
    """A timeout or connection failure never produces a status, so outcome is the only signal."""
    upstream.side_effect = httpx2.ConnectTimeout("upstream down")

    with pytest.raises(UpstreamError):
        await pesu.authenticate("u", "p")

    snapshot = collector.snapshot()
    assert snapshot.value(UPSTREAM_REQUESTS.name, operation="login", outcome="error") == 1.0
    assert snapshot.value(UPSTREAM_REQUESTS.name, operation="login", outcome="success") == 0.0
    assert list(snapshot.samples(UPSTREAM_RESPONSES.name)) == []


@pytest.mark.asyncio
async def test_a_failed_profile_status_is_still_a_successful_call(
    pesu, collector, upstream, make_response, login_payload
):
    """The call reached PESU and got an answer; it is the answer that was wrong."""
    upstream.side_effect = [make_response(json=login_payload), make_response(500)]

    with pytest.raises(ProfileFetchError):
        await pesu.authenticate("u", "p", profile=True)

    snapshot = collector.snapshot()
    assert snapshot.value(UPSTREAM_REQUESTS.name, operation="profile_fetch", outcome="success") == 1.0
    assert snapshot.value(UPSTREAM_RESPONSES.name, operation="profile_fetch", status="500") == 1.0


@pytest.mark.asyncio
async def test_a_cancelled_upstream_call_is_not_counted_as_an_error(pesu, collector, upstream):
    """A disconnect or a shutdown is not PESU failing.

    Counting cancellation as an upstream error would spike the error rate on every deploy and every
    abandoned request, which is exactly when someone is looking at the dashboard.
    """
    upstream.side_effect = asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await pesu.authenticate("u", "p")

    snapshot = collector.snapshot()
    assert snapshot.value(UPSTREAM_REQUESTS.name, operation="login", outcome="cancelled") == 1.0
    assert snapshot.value(UPSTREAM_REQUESTS.name, operation="login", outcome="error") == 0.0
    # Still timed, so the three outcomes always sum to the number of calls attempted
    assert snapshot.value(f"{UPSTREAM_LATENCY.name}_count", operation="login") == 1.0
    # And the client is still closed
    assert snapshot.value(HTTP_CLIENTS.name, event="closed") == 1.0


@pytest.mark.asyncio
async def test_closing_a_client_is_recorded(collector):
    await _close_client_quietly(AsyncMock(), collector)
    assert collector.snapshot().value(HTTP_CLIENTS.name, event="closed") == 1.0


@pytest.mark.asyncio
async def test_a_client_that_refuses_to_close_is_recorded(collector, caplog):
    """created minus closed is the leak indicator, so a failed close cannot be counted as a close."""
    client = AsyncMock()
    client.aclose.side_effect = RuntimeError("refused")

    with caplog.at_level("WARNING"):
        await _close_client_quietly(client, collector)

    snapshot = collector.snapshot()
    assert snapshot.value(HTTP_CLIENTS.name, event="close_failed") == 1.0
    assert snapshot.value(HTTP_CLIENTS.name, event="closed") == 0.0
    assert "Failed to close an HTTP client cleanly." in caplog.text


@pytest.mark.asyncio
async def test_a_close_that_fails_does_not_replace_the_original_error(
    pesu, collector, upstream, make_response, monkeypatch
):
    """Cleanup failure must not turn a routine 401 into a 500."""
    upstream.side_effect = [make_response(401, json={"statusCode": 401})]
    monkeypatch.setattr("app.pesu.httpx2.AsyncClient.aclose", AsyncMock(side_effect=RuntimeError("refused")))

    with pytest.raises(AuthenticationError):
        await pesu.authenticate("u", "wrong")

    assert collector.snapshot().value(HTTP_CLIENTS.name, event="close_failed") == 1.0


def test_a_bare_pesu_academy_still_works():
    """Tests and scripts construct PESUAcademy() directly; it must not require a collector."""
    assert PESUAcademy()._metrics is not None


@pytest.mark.asyncio
async def test_field_filtering_is_recorded_at_the_branch(
    pesu, collector, upstream, make_response, login_payload, profile_payload
):
    """Recorded where the branch is taken, not from the request body.

    A caller who passes exactly the default field list has specified fields but triggers no
    filtering, so reading the request body would report the wrong thing.
    """
    upstream.side_effect = [
        make_response(json=payload) for _ in range(3) for payload in (login_payload, profile_payload)
    ]

    await pesu.authenticate("u", "p", profile=True, fields=["name", "rollNumber"])
    await pesu.authenticate("u", "p", profile=True, fields=None)
    await pesu.authenticate("u", "p", profile=True, fields=list(pesu.DEFAULT_FIELDS))

    snapshot = collector.snapshot()
    assert snapshot.value(PROFILE_FIELD_FILTERING.name, enabled="true") == 1.0
    # None and an explicit copy of the defaults both mean "no filtering happened"
    assert snapshot.value(PROFILE_FIELD_FILTERING.name, enabled="false") == 2.0
