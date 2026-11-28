"""Request ID propagation and logging context helpers."""

import contextvars
import logging
import re
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from fastapi.requests import Request
    from fastapi.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"
MAX_REQUEST_ID_LENGTH = 128
# The ID goes into every log line, so only characters that cannot break or fake a line are accepted
REQUEST_ID_REQUIREMENTS = re.compile(r"\A[A-Za-z0-9._-]+\Z")
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)


def resolve_request_id(incoming_id: str | None) -> str:
    """Return the caller's request ID if it is safe to log, or a new one.

    Args:
        incoming_id (str | None): The X-Request-ID header the caller sent, if any.

    Returns:
        str: The caller's ID, or a UUID4 hex string if it is missing, too long or has other characters.
    """
    if (
        incoming_id
        and len(incoming_id) <= MAX_REQUEST_ID_LENGTH
        and REQUEST_ID_REQUIREMENTS.match(incoming_id) is not None
    ):
        return incoming_id
    return uuid.uuid4().hex


class RequestIdFilter(logging.Filter):
    """Attach the active request ID from context to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add the active request ID to a record, or `-` outside a request.

        Args:
            record (logging.LogRecord): The record being logged.

        Returns:
            bool: Always True: the filter only adds a field, and never drops a record.
        """
        record.request_id = request_id_var.get() or "-"
        return True


async def request_id_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Bind the request's ID for everything that logs while it is handled, and return it in the response.

    Args:
        request (Request): The incoming request.
        call_next (Callable[[Request], Awaitable[Response]]): The rest of the app.

    Returns:
        Response: The app's response, with the X-Request-ID header set.
    """
    request_id = resolve_request_id(request.headers.get(REQUEST_ID_HEADER))
    token = request_id_var.set(request_id)
    # Not reset if the route raises: ServerErrorMiddleware renders that 500 above this middleware, in the same
    # task, and its handler needs the ID. Each request runs in a task of its own, so the ID ends with it.
    response = await call_next(request)
    request_id_var.reset(token)
    response.headers[REQUEST_ID_HEADER] = request_id
    return response
