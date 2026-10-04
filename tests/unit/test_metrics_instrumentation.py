"""Tests that the instrumentation records what it claims, path by path."""

from unittest.mock import AsyncMock, patch

import pytest
import snapshot

from app.exceptions.authentication import CSRFTokenError, ProfileFetchError, ProfileParseError
from app.metrics.collector import (
    CSRF_CACHE,
    HTTP_CLIENTS,
    PREFETCH_TASKS,
    PROFILE_PARSE_ERRORS,
    UPSTREAM_LATENCY,
    UPSTREAM_REQUESTS,
    UPSTREAM_RESPONSES,
    MetricsCollector,
)
from app.pesu import PESUAcademy, _upstream_call


@pytest.fixture
def collector():
    return MetricsCollector(clock=lambda: 1000.0)


@pytest.fixture
def pesu(collector):
    return PESUAcademy(collector)


def _response(text="", status=200):
    response = AsyncMock()
    response.text = text
    response.status_code = status
    return response


@pytest.mark.asyncio
@patch("app.pesu.httpx2.AsyncClient.get")
async def test_a_csrf_fetch_records_the_upstream_call(mock_get, pesu, collector):
    mock_get.return_value = _response('<meta name="csrf-token" content="tok">')
    await pesu._fetch_new_client_with_csrf_token()
    snapshot = collector.snapshot()
    assert snapshot.value(UPSTREAM_REQUESTS.name, operation="csrf_fetch", outcome="success") == 1.0
    assert snapshot.value(UPSTREAM_RESPONSES.name, operation="csrf_fetch", status="200") == 1.0
    assert snapshot.value(f"{UPSTREAM_LATENCY.name}_count", operation="csrf_fetch") == 1.0
    assert snapshot.value(HTTP_CLIENTS.name, event="created") == 1.0


@pytest.mark.asyncio
@patch("app.pesu.httpx2.AsyncClient.get")
async def test_a_failing_csrf_fetch_is_recorded_as_an_error(mock_get, pesu, collector):
    """A timeout or connection failure never produces a status, so outcome is the only signal."""
    mock_get.side_effect = RuntimeError("upstream down")
    with pytest.raises(RuntimeError):
        await pesu._fetch_new_client_with_csrf_token()
    snapshot = collector.snapshot()
    assert snapshot.value(UPSTREAM_REQUESTS.name, operation="csrf_fetch", outcome="error") == 1.0
    assert snapshot.value(UPSTREAM_REQUESTS.name, operation="csrf_fetch", outcome="success") == 0.0
    assert list(snapshot.samples(UPSTREAM_RESPONSES.name)) == []


@pytest.mark.asyncio
@patch("app.pesu.httpx2.AsyncClient.get")
async def test_a_missing_csrf_tag_still_counts_the_call_as_a_success(mock_get, pesu, collector):
    """The call reached PESU and got a 200; it is our parsing that failed, not the upstream."""
    mock_get.return_value = _response("<html>no token here</html>")
    with pytest.raises(CSRFTokenError):
        await pesu._fetch_new_client_with_csrf_token()
    snapshot = collector.snapshot()
    assert snapshot.value(UPSTREAM_REQUESTS.name, operation="csrf_fetch", outcome="success") == 1.0
    # The client could not be handed to anyone, so it must have been closed
    assert snapshot.value(HTTP_CLIENTS.name, event="closed") == 1.0


@pytest.mark.asyncio
@patch("app.pesu.PESUAcademy._fetch_new_client_with_csrf_token")
async def test_a_warm_cache_is_recorded_as_a_hit(mock_fetch, pesu, collector):
    mock_fetch.return_value = (AsyncMock(), "token")
    pesu._client, pesu._csrf_token = AsyncMock(), "cached"
    await pesu._get_client_with_csrf_token()
    assert collector.snapshot().value(CSRF_CACHE.name, outcome="hit") == 1.0


@pytest.mark.asyncio
@patch("app.pesu.PESUAcademy._fetch_new_client_with_csrf_token")
async def test_a_cold_cache_is_recorded_as_a_miss(mock_fetch, pesu, collector):
    """A miss means the caller waited on the upstream round trip the prefetch exists to avoid."""
    mock_fetch.return_value = (AsyncMock(), "token")
    await pesu._get_client_with_csrf_token()
    assert collector.snapshot().value(CSRF_CACHE.name, outcome="miss") == 1.0


@pytest.mark.asyncio
@patch("app.pesu.PESUAcademy._fetch_new_client_with_csrf_token")
async def test_a_successful_prefetch_is_recorded(mock_fetch, pesu, collector):
    import asyncio

    mock_fetch.return_value = (AsyncMock(), "token")
    pesu._spawn_prefetch_task()
    await asyncio.gather(*tuple(pesu._prefetch_tasks), return_exceptions=True)
    await asyncio.sleep(0)
    assert collector.snapshot().value(PREFETCH_TASKS.name, outcome="success") == 1.0


@pytest.mark.asyncio
@patch("app.pesu.PESUAcademy._fetch_new_client_with_csrf_token")
async def test_a_failed_prefetch_is_recorded(mock_fetch, pesu, collector):
    import asyncio

    mock_fetch.side_effect = RuntimeError("upstream down")
    pesu._spawn_prefetch_task()
    await asyncio.gather(*tuple(pesu._prefetch_tasks), return_exceptions=True)
    await asyncio.sleep(0)
    assert collector.snapshot().value(PREFETCH_TASKS.name, outcome="failure") == 1.0


@pytest.mark.asyncio
async def test_closing_a_client_is_recorded(pesu, collector):
    client = AsyncMock()
    pesu._client = client
    await pesu.close_client()
    assert collector.snapshot().value(HTTP_CLIENTS.name, event="closed") == 1.0


@pytest.mark.asyncio
async def test_a_client_that_refuses_to_close_is_recorded(pesu, collector):
    """created minus closed is the leak indicator, so a failed close cannot be counted as a close."""
    client = AsyncMock()
    client.aclose.side_effect = RuntimeError("refused")
    pesu._client = client
    await pesu.close_client()
    snapshot = collector.snapshot()
    assert snapshot.value(HTTP_CLIENTS.name, event="close_failed") == 1.0
    assert snapshot.value(HTTP_CLIENTS.name, event="closed") == 0.0


@pytest.mark.asyncio
async def test_a_profile_fetch_records_its_upstream_call(pesu, collector):
    client = AsyncMock()
    client.get.return_value = _response("<html></html>", status=500)
    with pytest.raises(ProfileFetchError):
        await pesu.get_profile_information(client, "user")
    snapshot = collector.snapshot()
    assert snapshot.value(UPSTREAM_REQUESTS.name, operation="profile_fetch", outcome="success") == 1.0
    assert snapshot.value(UPSTREAM_RESPONSES.name, operation="profile_fetch", status="500") == 1.0


@pytest.mark.asyncio
async def test_an_unparseable_profile_page_records_a_reason(pesu, collector):
    client = AsyncMock()
    client.get.return_value = _response("<html><body>nothing useful</body></html>")
    with pytest.raises(ProfileParseError):
        await pesu.get_profile_information(client, "user")
    assert collector.snapshot().value(PROFILE_PARSE_ERRORS.name, reason="page_structure") == 1.0


def test_a_bare_pesu_academy_still_works():
    """Tests and scripts construct PESUAcademy() directly; it must not require a collector."""
    assert PESUAcademy()._metrics is not None


@pytest.mark.asyncio
@patch("app.pesu.httpx2.AsyncClient.get")
async def test_a_cancelled_upstream_call_is_not_counted_as_an_error(mock_get, pesu, collector):
    """A disconnect or a shutdown is not PESU failing.

    Counting cancellation as an upstream error would spike the error rate on every deploy and every
    abandoned request, which is exactly when someone is looking at the dashboard.
    """
    import asyncio

    mock_get.side_effect = asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        await pesu._fetch_new_client_with_csrf_token()
    snapshot = collector.snapshot()
    assert snapshot.value(UPSTREAM_REQUESTS.name, operation="csrf_fetch", outcome="cancelled") == 1.0
    assert snapshot.value(UPSTREAM_REQUESTS.name, operation="csrf_fetch", outcome="error") == 0.0
    # Still timed, so the three outcomes always sum to the number of calls attempted
    assert snapshot.value(f"{UPSTREAM_LATENCY.name}_count", operation="csrf_fetch") == 1.0


@pytest.mark.asyncio
@patch("app.pesu.PESUAcademy.get_profile_information")
@patch("app.pesu.PESUAcademy._get_client_with_csrf_token")
async def test_field_filtering_is_recorded_at_the_branch(mock_client, mock_profile, pesu, collector):
    """Recorded where the branch is taken, not from the request body.

    A caller who passes exactly the default field list has specified fields but triggers no
    filtering, so reading the request body would report the wrong thing.
    """
    from app.metrics.collector import PROFILE_FIELD_FILTERING

    client = AsyncMock()
    client.post.return_value = _response('<meta name="csrf-token" content="new">')
    mock_client.return_value = (client, "token")
    mock_profile.return_value = {"name": "Test", "prn": "PES1", "email": "a@b.com"}

    await pesu.authenticate("u", "p", profile=True, fields=["name"])
    await pesu.authenticate("u", "p", profile=True, fields=None)
    await pesu.authenticate("u", "p", profile=True, fields=list(pesu.DEFAULT_FIELDS))

    snapshot = collector.snapshot()
    assert snapshot.value(PROFILE_FIELD_FILTERING.name, enabled="true") == 1.0
    # None and an explicit copy of the defaults both mean "no filtering happened"
    assert snapshot.value(PROFILE_FIELD_FILTERING.name, enabled="false") == 2.0


@pytest.mark.asyncio
@patch("app.pesu.PESUAcademy.get_profile_information")
@patch("app.pesu.PESUAcademy._get_client_with_csrf_token")
async def test_a_login_records_its_upstream_call(mock_client, mock_profile, pesu, collector):
    client = AsyncMock()
    client.post.return_value = _response('<meta name="csrf-token" content="new">')
    mock_client.return_value = (client, "token")
    mock_profile.return_value = {"name": "Test"}

    await pesu.authenticate("u", "p")

    snapshot = collector.snapshot()
    assert snapshot.value(UPSTREAM_REQUESTS.name, operation="login", outcome="success") == 1.0
    assert snapshot.value(UPSTREAM_RESPONSES.name, operation="login", status="200") == 1.0
    # The client this request borrowed is closed on the way out, on every path
    assert snapshot.value(HTTP_CLIENTS.name, event="closed") == 1.0


@pytest.mark.asyncio
@patch("app.pesu.PESUAcademy._get_client_with_csrf_token")
async def test_a_wrong_password_still_counts_the_login_as_reaching_pesu(mock_client, pesu, collector):
    """PESU answered with a 200 and a login form. The call worked; the credentials did not."""
    from app.exceptions.authentication import AuthenticationError

    client = AsyncMock()
    client.post.return_value = _response('<div class="login-form"></div>')
    mock_client.return_value = (client, "token")

    with pytest.raises(AuthenticationError):
        await pesu.authenticate("u", "wrong")

    snapshot = collector.snapshot()
    assert snapshot.value(UPSTREAM_REQUESTS.name, operation="login", outcome="success") == 1.0
    assert snapshot.value(UPSTREAM_REQUESTS.name, operation="login", outcome="error") == 0.0

@pytest.mark.asyncio
async def test_upstream_call_without_appending(collector):
    async with _upstream_call(collector, "csrf_fetch") as sink:
        pass
    snapshot = collector.snapshot()
    assert snapshot.value(UPSTREAM_REQUESTS.name, operation="csrf_fetch", outcome="success") == 1.0
    assert snapshot.value(UPSTREAM_REQUESTS.name, operation="csrf_fetch", outcome="error") == 0.0
    assert snapshot.value(f"{UPSTREAM_LATENCY.name}_count", operation="csrf_fetch") == 1.0
    assert list(snapshot.samples(UPSTREAM_RESPONSES.name)) == []

@pytest.mark.asyncio
async def test_upstream_call_with_test_subject(collector):
    async with _upstream_call(collector, "csrf_fetch") as sink:
        sink.append(object())
    snapshot = collector.snapshot()
    assert snapshot.value(UPSTREAM_REQUESTS.name, operation="csrf_fetch", outcome="success") == 1.0
    assert snapshot.value(UPSTREAM_REQUESTS.name, operation="csrf_fetch", outcome="error") == 0.0
    assert snapshot.value(f"{UPSTREAM_LATENCY.name}_count", operation="csrf_fetch") == 1.0
    assert list(snapshot.samples(UPSTREAM_RESPONSES.name)) == []
