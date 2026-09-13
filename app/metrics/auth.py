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

# Read once at import, so whether this process enforces a token is fixed for its lifetime and
# cannot start or stop halfway through. An empty value counts as unset, which is what an
# environment variable declared but left blank looks like.
METRICS_TOKEN: str | None = os.environ.get("METRICS_TOKEN") or None

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
    # long the comparison took
    if credentials is None or not secrets.compare_digest(credentials.credentials, expected):
        raise MetricsAuthorizationError
