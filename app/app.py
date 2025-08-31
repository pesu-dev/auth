"""FastAPI Entrypoint for PESUAuth API."""

import argparse
import asyncio
import datetime
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytz
import uvicorn
from fastapi import BackgroundTasks, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import ValidationError

from app.docs import authenticate_docs, health_docs, readme_docs
from app.docs.metrics import metrics_docs
from app.exceptions.base import PESUAcademyError
from app.metrics import metrics  # Global metrics instance
from app.models import RequestModel, ResponseModel
from app.pesu import PESUAcademy

IST = pytz.timezone("Asia/Kolkata")
CSRF_TOKEN_REFRESH_INTERVAL_SECONDS = 45 * 60
CSRF_TOKEN_REFRESH_LOCK = asyncio.Lock()


async def _refresh_csrf_token_with_lock() -> None:
    """Refresh the CSRF token with a lock."""
    logging.debug("Refreshing unauthenticated CSRF token...")
    async with CSRF_TOKEN_REFRESH_LOCK:
        try:
            await pesu_academy.prefetch_client_with_csrf_token()
            metrics.inc("csrf_token_refresh_success_total")
            logging.info("Unauthenticated CSRF token refreshed successfully.")
        except Exception:
            metrics.inc("csrf_token_refresh_failure_total")
            raise


async def _csrf_token_refresh_loop() -> None:
    """Background task to refresh the CSRF token periodically."""
    while True:
        try:
            logging.debug("Refreshing unauthenticated CSRF token...")
            await _refresh_csrf_token_with_lock()
        except Exception:
            metrics.inc("csrf_token_refresh_failure_total")
            logging.exception("Failed to refresh unauthenticated CSRF token in the background.")
        await asyncio.sleep(CSRF_TOKEN_REFRESH_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan event handler for startup and shutdown events."""
    # Startup
    logging.info("PESUAuth API startup")

    # Prefetch PESUAcademy client for first request
    await pesu_academy.prefetch_client_with_csrf_token()
    logging.info("Prefetched a new PESUAcademy client with an unauthenticated CSRF token.")

    # Start the periodic CSRF token refresh background task
    refresh_task = asyncio.create_task(_csrf_token_refresh_loop())
    logging.info("Started the unauthenticated CSRF token refresh background task.")

    yield

    # Shutdown
    refresh_task.cancel()
    try:
        await refresh_task
    except asyncio.CancelledError:
        logging.debug("Unauthenticated CSRF token refresh background task cancelled.")
    except Exception:
        logging.exception("Failed to cancel unauthenticated CSRF token refresh background task.")

    await pesu_academy.close_client()
    logging.info("PESUAuth API shutdown.")


app = FastAPI(
    title="PESUAuth API",
    description="A simple and lightweight API to authenticate PESU credentials using PESU Academy",
    version="2.1.0",
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
pesu_academy = PESUAcademy()


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handler for request validation errors."""
    metrics.inc("validation_error_total")
    logging.exception("Request data could not be validated.")
    errors = exc.errors()
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
    metrics.inc("pesu_academy_error_total")

    # Track specific error types
    exc_type = type(exc).__name__.lower()
    if "csrf" in exc_type:
        metrics.inc("csrf_token_error_total")
    elif "profile_fetch" in exc_type:
        metrics.inc("profile_fetch_error_total")
    elif "profile_parse" in exc_type:
        metrics.inc("profile_parse_error_total")
    elif "authentication" in exc_type:
        metrics.inc("auth_failure_total")

    logging.exception(f"PESUAcademyError: {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": False,
            "message": exc.message,
            "timestamp": datetime.datetime.now(IST).isoformat(),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handler for unhandled exceptions."""
    metrics.inc("unhandled_exception_total")
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
    response_class=JSONResponse,
    responses=metrics_docs.response_examples,
    tags=["Monitoring"],
)
async def get_metrics() -> JSONResponse:
    """Get current application metrics."""
    logging.debug("Metrics requested.")
    current_metrics = metrics.get()
    return JSONResponse(
        status_code=200,
        content={
            "status": True,
            "message": "Metrics retrieved successfully",
            "timestamp": datetime.datetime.now(IST).isoformat(),
            "metrics": current_metrics,
        },
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
async def authenticate(payload: RequestModel, background_tasks: BackgroundTasks) -> JSONResponse:
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
    logging.info(f"Authenticating user={username} with PESU Academy...")

    authentication_result.update(
        await pesu_academy.authenticate(
            username=username,
            password=password,
            profile=profile,
            fields=fields,
        ),
    )

    # Prefetch a new client with an unauthenticated CSRF token for the next request
    background_tasks.add_task(_refresh_csrf_token_with_lock)

    # Validate the response
    try:
        authentication_result = ResponseModel.model_validate(authentication_result)
        logging.info(f"Returning auth result for user={username}: {authentication_result}")
        authentication_result = authentication_result.model_dump(exclude_none=True)
        authentication_result["timestamp"] = current_time.isoformat()

        # Track successful authentication only after validation succeeds
        metrics.inc("auth_success_total")

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
