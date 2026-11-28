import asyncio
import logging
import uuid
from types import SimpleNamespace

import pytest

from app.request_id import (
    REQUEST_ID_HEADER,
    RequestIdFilter,
    request_id_middleware,
    request_id_var,
    resolve_request_id,
)


async def handle(sent_id):
    """Run a request through the middleware, with `sent_id` as its header unless it is None.

    Returns the IDs the app saw while handling it, and the ID in the response.
    """
    seen = []
    response = SimpleNamespace(headers={})

    async def call_next(_request):
        seen.append(request_id_var.get())
        return response

    headers = {} if sent_id is None else {REQUEST_ID_HEADER: sent_id}
    await request_id_middleware(SimpleNamespace(headers=headers), call_next)
    return seen, response.headers[REQUEST_ID_HEADER]


def test_valid_id_string(valid_request_id):
    assert resolve_request_id(valid_request_id) == valid_request_id


def test_invalid_id_falls_back_to_uuid(invalid_request_id):
    result = resolve_request_id(invalid_request_id)
    assert result != invalid_request_id
    assert uuid.UUID(result, version=4).hex == result


def test_request_id_filter_outside_request():
    record = logging.makeLogRecord({})
    assert RequestIdFilter().filter(record) is True
    assert record.request_id == "-"


def test_request_id_filter_with_active_id(valid_request_id):
    record = logging.makeLogRecord({})
    token = request_id_var.set(valid_request_id)
    try:
        assert RequestIdFilter().filter(record) is True
    finally:
        request_id_var.reset(token)
    assert record.request_id == valid_request_id


@pytest.mark.asyncio
async def test_request_id_middleware_echoes_valid_header(valid_request_id):
    seen, returned = await handle(valid_request_id)
    assert seen == [valid_request_id]
    assert returned == valid_request_id
    assert request_id_var.get() is None


@pytest.mark.asyncio
async def test_request_id_middleware_generates_uuid_on_invalid_header(invalid_request_id):
    seen, returned = await handle(invalid_request_id)
    assert seen == [returned]
    assert returned != invalid_request_id
    assert uuid.UUID(returned, version=4).hex == returned
    assert request_id_var.get() is None


@pytest.mark.asyncio
async def test_request_id_middleware_isolates_concurrent_requests():
    seen = {}

    async def run_one(request_id):
        async def call_next(_request):
            seen[request_id] = [request_id_var.get()]
            # Lets the other request run in between, so a shared ID would show up here
            await asyncio.sleep(0)
            seen[request_id].append(request_id_var.get())
            return SimpleNamespace(headers={})

        response = await request_id_middleware(SimpleNamespace(headers={REQUEST_ID_HEADER: request_id}), call_next)
        return response.headers[REQUEST_ID_HEADER]

    assert await asyncio.gather(run_one("req-id-1"), run_one("req-id-2")) == ["req-id-1", "req-id-2"]
    assert seen == {"req-id-1": ["req-id-1", "req-id-1"], "req-id-2": ["req-id-2", "req-id-2"]}
    assert request_id_var.get() is None
