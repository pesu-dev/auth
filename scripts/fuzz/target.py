"""Run the real application with an isolated, entirely synthetic PESU backend."""

from __future__ import annotations

from contextlib import contextmanager
from importlib import import_module
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import uvicorn

from app.exceptions.authentication import AuthenticationError
from app.metrics.collector import MetricsCollector
from app.pesu import PESUAcademy

if TYPE_CHECKING:
    from collections.abc import Iterator

    from fastapi import FastAPI

SYNTHETIC_TOKEN = "secret-token"  # Only synthetic fixtures may be shown in unsanitized reproduction commands.
SYNTHETIC_USERNAME = "fuzz-user"
SYNTHETIC_PROFILE: dict[str, str | int] = {
    "name": "Fuzz Student",
    "prn": "SYNTHETIC-PRN",
    "srn": "SYNTHETIC-SRN",
    "program": "Bachelor of Technology",
    "branch": "Computer Science and Engineering",
    "semester": "2",
    "section": "A",
    "email": "fuzz@example.invalid",
    "phone": "0000000000",
    "campusCode": 1,
    "campus": "RR",
}


async def _authenticate(
    username: str,
    password: str,
    profile: bool = False,
    fields: list[str] | None = None,
) -> dict[str, Any]:
    """Return synthetic profiles for one username and reject every other username.

    Args:
        username (str): The synthetic username accepted by this target.
        password (str): Any nonempty synthetic password validated by the request model.
        profile (bool): Whether to include the synthetic profile.
        fields (list[str] | None): Optional subset of profile fields.

    Returns:
        dict[str, Any]: An authentication result consumed by the real route.

    Raises:
        AuthenticationError: If the username is not the synthetic account.
    """
    if username != SYNTHETIC_USERNAME:
        raise AuthenticationError
    result: dict[str, Any] = {"status": True, "message": "Login successful."}
    if profile:
        result["profile"] = {key: value for key, value in SYNTHETIC_PROFILE.items() if fields is None or key in fields}
    return result


async def _reject_upstream(*args: object, **kwargs: object) -> None:
    """Fail immediately if the mocked target accidentally attempts an upstream request.

    Args:
        *args (object): Discarded request positional arguments.
        **kwargs (object): Discarded request keyword arguments.

    Raises:
        AssertionError: Always, because this target must remain offline.
    """
    raise AssertionError("The synthetic fuzz target must never make upstream HTTP requests.")


@contextmanager
def mocked_app(token: str | None = SYNTHETIC_TOKEN) -> Iterator[FastAPI]:
    """Isolate all shared state while replacing only the PESU backend.

    The caller owns the application's real lifespan. Keep this context open until that lifespan
    exits so startup, refresh tasks, requests, and shutdown all see the mocked backend.

    Args:
        token (str | None): Synthetic metrics token, or None for the open metrics endpoint.

    Yields:
        FastAPI: The real app, with request handling and metrics instrumentation intact.
    """
    app_module = import_module("app.app")
    application = app_module.app
    collector = MetricsCollector()
    backend = PESUAcademy(collector)
    original_schema = application.openapi_schema
    try:
        application.openapi_schema = None
        with (
            patch.object(app_module, "metrics", collector),
            patch.object(app_module, "pesu_academy", backend),
            patch("app.metrics.auth.METRICS_TOKEN", token),
            patch.object(backend, "prefetch_client_with_csrf_token", new_callable=AsyncMock),
            patch.object(backend, "close_client", new_callable=AsyncMock),
            patch.object(backend, "authenticate", _authenticate),
            patch("httpx2.AsyncClient.request", _reject_upstream),
        ):
            yield application
    finally:
        application.openapi_schema = original_schema


def main() -> None:
    """Serve the mocked target on loopback for URL-based pytest and CLI runs."""
    with mocked_app() as application:
        uvicorn.run(application, host="127.0.0.1", port=8080, log_level="warning", access_log=False)


if __name__ == "__main__":
    main()
