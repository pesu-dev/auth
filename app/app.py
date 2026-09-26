"""FastAPI Entrypoint for PESUAuth API."""

from __future__ import annotations

import argparse
import asyncio
import datetime
import logging
import os
from contextlib import asynccontextmanager
from importlib.metadata import version
from typing import TYPE_CHECKING, Any, Literal
from zoneinfo import ZoneInfo

import uvicorn
from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi.requests import Request
    from fastapi.responses import Response
    from starlette.middleware.base import RequestResponseEndpoint

from pydantic import ValidationError

from app.docs import authenticate_docs, health_docs, metrics_docs, readme_docs
from app.exceptions.base import PESUAcademyError
from app.metrics.auth import require_metrics_token
from app.metrics.collector import (
    AUTHENTICATION_REQUESTS,
    AUTHENTICATION_RESULTS,
    CSRF_REFRESHES,
    ERRORS_BY_TYPE,
    LIFESPAN_EVENTS,
    VALIDATION_ERRORS,
    MetricsCollector,
)
from app.metrics.middleware import record_request_metrics
from app.metrics.prometheus import PROMETHEUS_CONTENT_TYPE, MetricsFormat, render_prometheus
from app.models import HealthChecksModel, HealthModel, MetricsModel, RequestModel, ResponseModel
from app.pesu import PESUAcademy

IST = ZoneInfo("Asia/Kolkata")

EnvironmentName = Literal["development", "staging", "production"]
ALLOWED_ENVIRONMENTS: frozenset[str] = frozenset({"development", "staging", "production"})


def resolve_environment(value: str | None = None) -> EnvironmentName:
    """Read and validate PESU_AUTH_ENVIRONMENT.

    Args:
        value (str | None): An explicit value to validate. When omitted, the process
            environment is read. An unset or empty value defaults to ``development``.

    Returns:
        EnvironmentName: One of ``development``, ``staging``, or ``production``.

    Raises:
        ValueError: If the value is set to anything other than the three allowed names.
    """
    raw = os.getenv("PESU_AUTH_ENVIRONMENT") if value is None else value
    if raw is None or raw == "":
        return "development"
    if raw not in ALLOWED_ENVIRONMENTS:
        allowed = ", ".join(sorted(ALLOWED_ENVIRONMENTS))
        raise ValueError(
            f"PESU_AUTH_ENVIRONMENT must be one of {allowed}; got {raw!r}."
        )
    return raw  # type: ignore[return-value]


APP_ENVIRONMENT = resolve_environment()
CSRF_TOKEN_REFRESH_INTERVAL_SECONDS = 45 * 60
# Validation failures are labelled by field, so the label set has to be closed against a caller who
# can put anything in the request body
KNOWN_REQUEST_FIELDS = frozenset({"username", "password", "profile", "fields", "fmt", "body"})


async def _refresh_csrf_token() -> None:
    """Refresh the cached unauthenticated CSRF token and client."""
    await pesu_academy.prefetch_client_with_csrf_token()
    logging.info("Unauthenticated CSRF token refreshed successfully.")


async def _csrf_token_refresh_loop() -> None:
    """Background task to refresh the CSRF token periodically."""
    while True:
        # Sleep first. `lifespan` has already primed the cache by the time this task starts, so
        # refreshing immediately would fetch a second token and throw away the one just prefetched
        # -- an extra upstream round trip on every single startup.
        await asyncio.sleep(CSRF_TOKEN_REFRESH_INTERVAL_SECONDS)
        try:
            logging.debug("Refreshing unauthenticated CSRF token...")
            await _refresh_csrf_token()
        except Exception:
            metrics.increment(CSRF_REFRESHES, outcome="failure")
            logging.exception("Failed to refresh unauthenticated CSRF token in the background.")
        else:
            metrics.increment(CSRF_REFRESHES, outcome="success")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan event handler for startup and shutdown events."""
    # Startup
    metrics.increment(LIFESPAN_EVENTS, event="startup")
    logging.info("PESUAuth API startup")

    # Prefetch PESUAcademy client for first request
    await pesu_academy.prefetch_client_with_csrf_token()
    logging.info("Prefetched a new PESUAcademy client with an unauthenticated CSRF token.")

    # Start the periodic CSRF token refresh background task
    refresh_task = asyncio.create_task(_csrf_token_refresh_loop())
    app.state.csrf_refresh_task = refresh_task
    app.state.environment = APP_ENVIRONMENT
    logging.info("Started the unauthenticated CSRF token refresh background task.")

    yield

    # Shutdown
    refresh_task = getattr(app.state, "csrf_refresh_task", refresh_task)
    refresh_task.cancel()
    try:
        await refresh_task
    except asyncio.CancelledError:
        logging.debug("Unauthenticated CSRF token refresh background task cancelled.")
    except Exception:
        logging.exception("Failed to cancel unauthenticated CSRF token refresh background task.")

    await pesu_academy.close_client()
    metrics.increment(LIFESPAN_EVENTS, event="shutdown")
    logging.info("PESUAuth API shutdown.")


app = FastAPI(
    title="PESUAuth API",
    description="A simple and lightweight API to authenticate PESU credentials using PESU Academy",
    version=version("pesu-auth"),
    docs_url="/",
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "Authentication",
            "description": "Operations related to logging in with PESU credentials.",
        },
        {
            "name": "Documentation",
            "description": "Render the README and other developer-facing docs.",
        },
        {
            "name": "Monitoring",
            "description": "Health checks and other monitoring endpoints.",
        },
    ],
)
metrics = MetricsCollector()
pesu_academy = PESUAcademy(metrics)


# Captured before the override below, so the schema is still built by FastAPI itself. Calling
# get_openapi() directly would mean restating the fourteen arguments FastAPI passes it, and
# silently dropping any that were added later or set on the app afterwards.
_build_openapi_schema = app.openapi


def _openapi_without_phantom_validation_errors() -> dict[str, Any]:
    """Build the OpenAPI schema without the 422 responses this API can never return.

    FastAPI documents a 422 carrying its own `HTTPValidationError` body on every route whose
    parameters can fail validation. This API never returns that: `validation_exception_handler`
    turns every `RequestValidationError` into a **400** with the same
    `{status, message, timestamp}` body as every other error. Leaving the 422 in Swagger would
    document a response that cannot occur, in a shape this API never emits.

    Only the auto-generated ones are removed. `/authenticate` genuinely returns a 422 for a profile
    parse failure and documents it with `ResponseModel`, so it is matched on its schema and kept.

    Returns:
        dict[str, Any]: The OpenAPI schema, cached on the app after the first call.
    """
    if app.openapi_schema:
        return app.openapi_schema
    schema = _build_openapi_schema()
    phantom = "#/components/schemas/HTTPValidationError"
    for operations in schema.get("paths", {}).values():
        for operation in operations.values():
            response = operation.get("responses", {}).get("422", {})
            content = response.get("content", {}).get("application/json", {})
            if content.get("schema", {}).get("$ref") == phantom:
                del operation["responses"]["422"]
    # Nothing references them once the phantom responses are gone
    for name in ("HTTPValidationError", "ValidationError"):
        schema.get("components", {}).get("schemas", {}).pop(name, None)
    app.openapi_schema = schema
    return schema


app.openapi = _openapi_without_phantom_validation_errors


@app.middleware("http")
async def metrics_middleware(request: Request, call_next: RequestResponseEndpoint) -> Response:
    """Record traffic metrics for every request."""
    # Looks the collector up on the module at call time rather than capturing it, so a test can
    # swap in a fresh one with monkeypatch.setattr("app.app.metrics", ...).
    return await record_request_metrics(metrics, request, call_next)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handler for request validation errors."""
    metrics.increment(ERRORS_BY_TYPE, type=type(exc).__name__)
    errors = exc.errors()
    # Which field was wrong, not just that something was. The field names are a fixed set, so the
    # label is bounded; anything unrecognised collapses into one bucket rather than opening the
    # key space to caller-controlled strings.
    for error in errors:
        location = error.get("loc") or ()
        field = str(location[-1]) if location else "unknown"
        metrics.increment(VALIDATION_ERRORS, field=field if field in KNOWN_REQUEST_FIELDS else "other")
    # Log only the shape of the failure, never the submitted values. Each entry from `errors()`
    # carries an "input" key which, for a missing required field, is the *entire request body* --
    # so logging it verbatim would write the user's password to the logs in plaintext.
    safe_errors = [{"type": e.get("type"), "loc": e.get("loc"), "msg": e.get("msg")} for e in errors]
    # A malformed request is the caller's mistake, not a server fault, so no stack trace
    logging.warning(f"Request data could not be validated: {safe_errors}")
    message = "; ".join([f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}" for e in errors])
    return JSONResponse(
        status_code=400,
        content={
            "status": False,
            "message": f"Could not validate request data - {message}",
            "timestamp": datetime.datetime.now(IST).isoformat(),
        },
    )


@app.exception_handler(PESUAcademyError)
async def pesu_exception_handler(request: Request, exc: PESUAcademyError) -> JSONResponse:
    """Handler for PESUAcademy specific errors."""
    metrics.increment(ERRORS_BY_TYPE, type=type(exc).__name__)
    # Severity follows the status code. A 4xx is an expected outcome -- a wrong password is the
    # API working correctly -- and logging one at ERROR with a traceback both buries real faults
    # and pages whoever alerts on the error rate. Only 5xx gets a stack trace.
    if exc.status_code < 500:
        logging.warning(f"{type(exc).__name__}: {exc.message}")
    else:
        logging.exception(f"{type(exc).__name__}: {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": False,
            "message": exc.message,
            "timestamp": datetime.datetime.now(IST).isoformat(),
        },
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handler for unhandled exceptions."""
    metrics.increment(ERRORS_BY_TYPE, type=type(exc).__name__)
    logging.exception("Unhandled exception occurred.")
    return JSONResponse(
        status_code=500,
        content={
            "status": False,
            "message": "Internal Server Error. Please try again later.",
            "timestamp": datetime.datetime.now(IST).isoformat(),
        },
    )


@app.get(
    "/health",
    response_class=JSONResponse,
    responses=health_docs.response_examples,
    tags=["Monitoring"],
)
async def health() -> JSONResponse:
    """Health check endpoint."""
    logging.debug("Health check requested.")
    refresh_task = getattr(app.state, "csrf_refresh_task", None)
    payload = HealthModel(
        status=True,
        message="ok",
        timestamp=datetime.datetime.now(IST),
        version=version("pesu-auth"),
        environment=getattr(app.state, "environment", APP_ENVIRONMENT),
        checks=HealthChecksModel(
            csrf_cache_ready=pesu_academy.is_csrf_cache_ready(),
            csrf_refresh_task_running=refresh_task is not None and not refresh_task.done(),
        ),
    )
    content = payload.model_dump(by_alias=True)
    content["timestamp"] = payload.timestamp.isoformat()
    return JSONResponse(status_code=200, content=content)


@app.get(
    "/metrics",
    # The response type depends on ?fmt, so it cannot be declared once. Both shapes are documented
    # in responses= instead, which is what Swagger renders anyway.
    response_model=None,
    responses=metrics_docs.response_examples,
    tags=["Monitoring"],
    # Enforced only when METRICS_TOKEN is set in the environment; open otherwise, which is what
    # every existing caller and the local Docker instructions expect.
    dependencies=[Depends(require_metrics_token)],
)
async def metrics_endpoint(fmt: MetricsFormat = MetricsFormat.PROMETHEUS) -> Response:
    """Expose the collected metrics.

    Query parameters:
    - fmt (str, optional): `prometheus` for the text exposition format (the default, since that is
      what a scraper expects from this path), or `json` for the same counters as JSON.
    """
    snapshot = metrics.snapshot()
    if fmt is MetricsFormat.JSON:
        # by_alias so the keys are camelCase like every other response this API returns
        return JSONResponse(
            status_code=200,
            content=MetricsModel.from_snapshot(snapshot).model_dump(by_alias=True),
        )
    return PlainTextResponse(
        content=render_prometheus(snapshot),
        media_type=PROMETHEUS_CONTENT_TYPE,
    )


@app.get(
    "/readme",
    response_class=RedirectResponse,
    status_code=308,
    responses=readme_docs.response_examples,
    tags=["Documentation"],
)
async def readme() -> RedirectResponse:
    """Redirect to the PESUAuth GitHub repository."""
    return RedirectResponse("https://github.com/pesu-dev/auth", status_code=308)


@app.post(
    "/authenticate",
    response_model=ResponseModel,
    response_class=JSONResponse,
    openapi_extra=authenticate_docs.request_examples,
    responses=authenticate_docs.response_examples,
    tags=["Authentication"],
)
async def authenticate(payload: RequestModel) -> JSONResponse:
    """Authenticate a user using their PESU credentials via the PESU Academy service.

    Request body parameters:
    - username (str): The user's SRN, PRN, email address, or phone number.
    - password (str): The user's password.
    - profile (bool, optional): Flag indicating whether to retrieve the user's profile information.
    - fields (List[str], optional): Specific profile fields to include in the response.
    """
    current_time = datetime.datetime.now(IST)
    # Input has already been validated by the RequestModel
    username = payload.username
    password = payload.password
    profile = payload.profile
    fields = payload.fields

    # Authenticate the user
    authentication_result = {"timestamp": current_time}
    # Recorded here rather than in the middleware: the profile flag lives in the request body, and
    # reading the body in middleware would consume the downstream receive channel and pull a
    # payload containing a plaintext password into another layer. How many auth requests arrive is
    # already answered by route_requests_total; only the split needs the body.
    metrics.increment(AUTHENTICATION_REQUESTS, profile=str(profile).lower())
    logging.info(f"Authenticating user={username} with PESU Academy...")
    try:
        authentication_result.update(
            await pesu_academy.authenticate(
                username=username,
                password=password,
                profile=profile,
                fields=fields,
            ),
        )
    except Exception:
        # The outcome only, never the reason. errors_total{type} already names the exception class,
        # and recording it a second time here meant two counters describing one event that had to
        # be kept in step by a hand-written mapping -- which would have drifted the first time
        # someone added an exception class and forgot the entry.
        #
        # This family exists for the one thing nothing else can answer: the login success rate,
        # with success and failure in one family sharing a denominator.
        metrics.increment(AUTHENTICATION_RESULTS, result="failure")
        raise
    metrics.increment(AUTHENTICATION_RESULTS, result="success")

    # Validate the response
    try:
        authentication_result = ResponseModel.model_validate(authentication_result)
        logging.info(f"Returning auth result for user={username}: {authentication_result}")
        authentication_result = authentication_result.model_dump(by_alias=True, exclude_none=True)
        authentication_result["timestamp"] = current_time.isoformat()
        return JSONResponse(
            status_code=200,
            content=authentication_result,
        )
    except ValidationError:
        logging.exception(f"Validation error on ResponseModel for user={username}.")
        raise PESUAcademyError(
            status_code=500,
            message="Internal Server Error. Please try again later.",
        )


def main() -> None:
    """Main function to run the FastAPI application with command line arguments."""
    # Set up argument parser for command line arguments
    parser = argparse.ArgumentParser(
        description="PESUAuth API - A simple API to authenticate PESU credentials using PESU Academy.",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to run the FastAPI application on. Default is 0.0.0.0",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port to run the FastAPI application on. Default is 5000",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Run the application in debug mode with detailed logging.",
    )
    args = parser.parse_args()

    # Set up logging configuration
    logging_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=logging_level,
        format="%(asctime)s - %(levelname)s - %(filename)s:%(funcName)s:%(lineno)d - %(message)s",
        filemode="w",
    )

    # Run the app
    uvicorn.run("app.app:app", host=args.host, port=args.port, reload=args.debug)


if __name__ == "__main__":  # pragma: no cover
    main()  # pragma: no cover
