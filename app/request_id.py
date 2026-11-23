import contextvars
import logging
import re
import uuid
from collections.abc import Awaitable, Callable

from fastapi.requests import Request
from fastapi.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"
MAX_REQUEST_ID_LENGTH = 128
REQUEST_ID_REQUIREMENTS = re.compile(r"\A[A-Za-z0-9._-]+\Z")
request_id_var = contextvars.ContextVar("request_id", default=None)


def resolve_request_id(incoming_id: str | None) -> str:
    if (
        incoming_id
        and len(incoming_id) <= MAX_REQUEST_ID_LENGTH
        and REQUEST_ID_REQUIREMENTS.match(incoming_id) is not None
    ):
        return incoming_id
    return uuid.uuid4().hex


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or "-"
        return True


async def request_id_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    request_id = resolve_request_id(request.headers.get(REQUEST_ID_HEADER))
    token = request_id_var.set(request_id)
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
    response.headers[REQUEST_ID_HEADER] = request_id
    return response
