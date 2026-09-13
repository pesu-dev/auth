"""Optional bearer-token protection for the metrics endpoint."""

from __future__ import annotations

import os
import secrets
from typing import Annotated

from fastapi import Security

# Imported at runtime on purpose, not under TYPE_CHECKING. FastAPI resolves a dependency's
# annotations with get_type_hints() when the route is built, and this module uses
# `from __future__ import annotations`, so a name that exists only for type checkers would be a
# NameError at import time rather than a typing nicety.
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.exceptions.metrics import MetricsAuthorizationError


def _configured_token() -> str | None:
    """Read the configured metrics token from the environment.

    Returns:
        str | None: The token, or None when it is unset or blank -- a variable declared and left
            empty means "no token", not "the empty token".
    """
    return os.environ.get("METRICS_TOKEN") or None


# Read once at import, so whether this process enforces a token is fixed for its lifetime and
# cannot start or stop halfway through.
METRICS_TOKEN: str | None = _configured_token()

# auto_error=False so this never raises by itself: every failure path -- no header, no scheme, no
# credentials, or a scheme that is not Bearer -- returns None, and the 401 is raised below as a
# PESUAcademyError. That is what keeps the body in this API's `{status, message, timestamp}` shape
# and gets the failure counted in errors_total. HTTPBasic cannot be used the same way; it raises
# HTTPException on a malformed credential regardless of auto_error, which would answer in
# Starlette's `{"detail": ...}` shape and bypass the error metric entirely.
_bearer = HTTPBearer(
    auto_error=False,
    scheme_name="MetricsToken",
    description=(
        "Set the METRICS_TOKEN environment variable on the server to require this token. While it "
        "is unset the endpoint is open and any credential here is ignored."
    ),
)


async def require_metrics_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(_bearer)] = None,
) -> None:
    """Reject the request unless it carries the configured metrics token.

    Args:
        credentials (HTTPAuthorizationCredentials | None): Parsed bearer credentials, or None when
            the request carried no usable `Authorization: Bearer` header.

    Raises:
        MetricsAuthorizationError: If a token is configured and the request did not present it.
    """
    # Looked up on the module at call time rather than captured, so a test can swap it with
    # monkeypatch.setattr("app.metrics.auth.METRICS_TOKEN", ...)
    expected = METRICS_TOKEN
    if expected is None:
        return
    # compare_digest, not ==, so a wrong token cannot be recovered a character at a time from how
    # long the comparison took.
    #
    # Compared as bytes, not str: compare_digest *raises TypeError* on a str holding any non-ASCII
    # character, so `Authorization: Bearer ü` would turn this 401 into a 500 with a logged
    # traceback -- something any caller could do at will, and it would land in
    # failures_total{fault="server"}, which is the one metric worth alerting on. A non-ASCII
    # METRICS_TOKEN was worse still: every request 500ed, including the correct one.
    #
    # The two codecs are not interchangeable. A header value reaches us already latin-1 decoded,
    # per the HTTP spec and every ASGI server, so encoding it back through latin-1 recovers the
    # exact bytes the client sent; the configured token comes from the environment as UTF-8, with
    # surrogates standing in for any byte sequence that was not valid UTF-8. Encoding each back the
    # way it arrived makes the comparison byte-exact, so a non-ASCII token works rather than
    # silently never matching.
    if credentials is None or not secrets.compare_digest(
        credentials.credentials.encode("latin-1", "replace"),
        expected.encode("utf-8", "surrogateescape"),
    ):
        raise MetricsAuthorizationError
