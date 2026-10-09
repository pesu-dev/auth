"""FastAPI Entrypoint for PESUAuth API."""

from __future__ import annotations

import argparse
import datetime
import logging
import os
from contextlib import asynccontextmanager
from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any
from zoneinfo import ZoneInfo

import uvicorn
from fastapi import Depends, FastAPI, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.routing import APIRoute

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

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
    ERRORS_BY_TYPE,
    LIFESPAN_EVENTS,
    VALIDATION_ERRORS,
    MetricsCollector,
)
from app.metrics.middleware import record_request_metrics
from app.metrics.prometheus import PROMETHEUS_CONTENT_TYPE, MetricsFormat, render_prometheus
from app.models import MetricsModel, RequestModel, ResponseModel
from app.pesu import PESUAcademy

IST = ZoneInfo("Asia/Kolkata")
# Validation failures are labelled by field, so the label set has to be closed against a caller who
# can put anything in the request body
KNOWN_REQUEST_FIELDS = frozenset({"username", "password", "profile", "fields", "fmt", "body"})


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Lifespan event handler for startup and shutdown events."""
    # Startup
    metrics.increment(LIFESPAN_EVENTS, event="startup")
    logging.info("PESUAuth API startup")

    yield

    # Shutdown
    metrics.increment(LIFESPAN_EVENTS, event="shutdown")
    logging.info("PESUAuth API shutdown.")


app = FastAPI(
    title="PESUAuth API",
    description="A simple and lightweight API to authenticate PESU credentials using PESU Academy",
    version=version("pesu-auth"),
    docs_url="/docs",
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "Authentication",
            "description": "Operations related to logging in with PESU credentials.",
        },
        {
            "name": "Documentation",
            "description": "Redirect to the project's README on GitHub.",
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
    response it cannot parse and documents it with `ResponseModel`, so it is matched on its schema and kept.

    The documented response examples are also put back as written: FastAPI drops every null from the
    schema, examples included, which would show a profile field with no value as absent, not null.

    Returns:
        dict[str, Any]: The OpenAPI schema, cached on the app after the first call.
    """
    if app.openapi_schema:
        return app.openapi_schema
    schema = _build_openapi_schema()
    _restore_documented_examples(schema)
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


def _restore_documented_examples(schema: dict[str, Any]) -> None:
    """Put each route's documented response examples back into the schema exactly as written.

    Args:
        schema (dict[str, Any]): The OpenAPI schema FastAPI built, changed in place.
    """
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods:
            responses = schema["paths"][route.path][method.lower()]["responses"]
            for code, documented in route.responses.items():
                for media_type, content in documented.get("content", {}).items():
                    examples = {key: content[key] for key in ("example", "examples") if key in content}
                    responses[str(code)]["content"][media_type].update(examples)


app.openapi = _openapi_without_phantom_validation_errors


app.add_route(
    "/",
    lambda request: FileResponse(Path(__file__).parent / "templates" / "playground.html"),
    methods=["GET"],
    include_in_schema=False,
)


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
    # The detail, where there is one, is for the log only: it names the user and says what PESU
    # Academy answered. The caller gets the fixed message the API documents.
    if exc.status_code < 500:
        logging.warning(f"{type(exc).__name__}: {exc.detail or exc.message}")
    else:
        logging.exception(f"{type(exc).__name__}: {exc.detail or exc.message}")
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
    return JSONResponse(
        status_code=200,
        content={
            "status": True,
            "message": "ok",
            "timestamp": datetime.datetime.now(IST).isoformat(),
        },
    )


@app.get(
    "/metrics",
    summary="Metrics",
    # The response type depends on ?fmt, so it cannot be declared once. Both shapes are documented
    # in responses= instead, which is what Swagger renders anyway.
    response_model=None,
    responses=metrics_docs.response_examples,
    tags=["Monitoring"],
    # Enforced only when METRICS_TOKEN is set in the environment; open otherwise, which is what
    # every existing caller and the local Docker instructions expect.
    dependencies=[Depends(require_metrics_token)],
)
async def metrics_endpoint(
    fmt: Annotated[
        MetricsFormat,
        Query(
            description=(
                "Response format. `prometheus` (the default) returns the Prometheus text "
                "exposition format for a scraper; `json` returns the same counters as JSON "
                "for a human or a script."
            )
        ),
    ] = MetricsFormat.PROMETHEUS,
) -> Response:
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
    """Authenticate a user with their PESU credentials, and optionally return their profile.

    The credentials are checked by signing in to PESU Academy. They are sent only there, and the
    password is never stored or logged.

    Request body parameters:
    - username (str): The user's SRN, PRN, email address, or phone number.
    - password (str): The user's password.
    - profile (bool, optional): Whether to also return the user's profile. Fetching it is a second
      call to PESU Academy, so the request takes longer. Defaults to false.
    - fields (List[str], optional): Which profile fields to return, from those listed in
      `ProfileModel`. Every field is returned when it is omitted. Only used when `profile` is true.
      Fields come back in `ProfileModel`'s order, whatever order they are asked for in, and a name
      that is not in `ProfileModel` is a 400.

    Every requested profile field is in the response, and is `null` when PESU Academy has no value
    for it, does not send it, or sends it in an unexpected shape.
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
        # exclude_unset rather than exclude_none, so that a requested profile field with no value is
        # still returned, as null. What was never set stays out of the response: the profile when it
        # was not requested, and any profile field the caller did not ask for.
        authentication_result = authentication_result.model_dump(by_alias=True, exclude_unset=True)
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


def _build_arg_parser() -> argparse.ArgumentParser:
    """Build the command line parser for running the API.

    Returns:
        argparse.ArgumentParser: The parser, with --host, --port and --debug.
    """
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
        default=os.environ.get("PORT", "5000"),
        help=(
            "Port to run the FastAPI application on. Can also be set with the "
            " PORT environment variable. Default is 5000."
        ),
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Run the application in debug mode with detailed logging.",
    )

    return parser


def main() -> None:
    """Main function to run the FastAPI application with command line arguments."""
    parser = _build_arg_parser()
    args = parser.parse_args()

    # Set up logging configuration
    logging_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=logging_level,
        format="%(asctime)s - %(levelname)s - %(filename)s:%(funcName)s:%(lineno)d - %(message)s",
    )

    # Run the app
    uvicorn.run("app.app:app", host=args.host, port=args.port, reload=args.debug)


if __name__ == "__main__":  # pragma: no cover
    main()  # pragma: no cover
