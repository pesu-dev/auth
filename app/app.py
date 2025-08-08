"""FastAPI Entrypoint for PESUAuth API."""

import argparse
import asyncio
import datetime
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytz
import uvicorn
from fastapi import BackgroundTasks, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import ValidationError
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.exceptions.base import PESUAcademyError
from app.health import health_checker
from app.middleware.logging import LoggingMiddleware, configure_logging, get_logger
from app.middleware.metrics import (
    MetricsMiddleware,
    metrics_endpoint,
    record_authentication_attempt,
    record_csrf_operation,
)
from app.middleware.rate_limiting import limiter, rate_limit_exceeded_handler
from app.models import RequestModel, ResponseModel
from app.pesu import PESUAcademy

# Configure logging
configure_logging()
logger = get_logger("app")

# Create conditional rate limiting decorator
def conditional_rate_limit(limit_setting: str) -> callable:
    """Apply rate limiting decorator only if rate limiting is enabled."""
    def decorator(func: callable) -> callable:
        if settings.rate_limit_enabled and limiter:
            return limiter.limit(limit_setting)(func)
        return func
    return decorator

IST = pytz.timezone("Asia/Kolkata")
CSRF_TOKEN_REFRESH_LOCK = asyncio.Lock()


async def _refresh_csrf_token_with_lock() -> None:
    """Refresh the CSRF token with a lock."""
    logger.debug("Refreshing unauthenticated CSRF token")
    record_csrf_operation("refresh_attempt")
    async with CSRF_TOKEN_REFRESH_LOCK:
        await pesu_academy.prefetch_client_with_csrf_token()
        record_csrf_operation("refresh_success")
        logger.info("Unauthenticated CSRF token refreshed successfully")


async def _csrf_token_refresh_loop() -> None:
    """Background task to refresh the CSRF token periodically."""
    while True:
        try:
            logger.debug("Starting periodic CSRF token refresh")
            await _refresh_csrf_token_with_lock()
        except Exception as e:
            logger.error("Failed to refresh unauthenticated CSRF token in the background", error=str(e))
            record_csrf_operation("refresh_error")
        await asyncio.sleep(settings.csrf_refresh_interval)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan event handler for startup and shutdown events."""
    # Startup
    logger.info("PESUAuth API startup", version=settings.app_version)

    # Prefetch PESUAcademy client for first request
    await pesu_academy.prefetch_client_with_csrf_token()
    record_csrf_operation("initial_fetch")
    logger.info("Prefetched a new PESUAcademy client with an unauthenticated CSRF token")

    # Start the periodic CSRF token refresh background task
    refresh_task = asyncio.create_task(_csrf_token_refresh_loop())
    logger.info("Started the unauthenticated CSRF token refresh background task")

    yield

    # Shutdown
    refresh_task.cancel()
    try:
        await refresh_task
    except asyncio.CancelledError:
        logger.debug("Unauthenticated CSRF token refresh background task cancelled")
    except Exception as e:
        logger.error("Failed to cancel unauthenticated CSRF token refresh background task", error=str(e))

    await pesu_academy.close_client()
    await health_checker.close()
    logger.info("PESUAuth API shutdown")


app = FastAPI(
    title=settings.app_name,
    description=settings.app_description,
    version=settings.app_version,
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
            "description": "Health checks, metrics, and other monitoring endpoints.",
        },
    ],
)

# Add middlewares
if settings.cors_enabled:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )

if settings.metrics_enabled:
    app.add_middleware(MetricsMiddleware)

# Add logging middleware
app.add_middleware(LoggingMiddleware)

# Add rate limiting
if settings.rate_limit_enabled:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

pesu_academy = PESUAcademy()


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handler for request validation errors."""
    logger.error("Request data could not be validated", errors=exc.errors())
    errors = exc.errors()
    message = "; ".join([f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}" for e in errors])
    return JSONResponse(
        status_code=400,
        content={
            "status": False,
            "message": f"Could not validate request data - {message}",
        },
    )


@app.exception_handler(PESUAcademyError)
async def pesu_exception_handler(request: Request, exc: PESUAcademyError) -> JSONResponse:
    """Handler for PESUAcademy specific errors."""
    logger.error("PESUAcademyError occurred", error=exc.message, status_code=exc.status_code)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": False,
            "message": exc.message,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handler for unhandled exceptions."""
    logger.error("Unhandled exception occurred", error=str(exc), error_type=type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content={
            "status": False,
            "message": "Internal Server Error. Please try again later.",
        },
    )


# Health check endpoints
@app.get("/health", tags=["Monitoring"])
@conditional_rate_limit(settings.rate_limit_health)
async def health_check(request: Request) -> JSONResponse:
    """Basic health check endpoint."""
    logger.debug("Basic health check requested")
    return JSONResponse(content={"status": "ok"})


@app.get("/health/detailed", tags=["Monitoring"])
@conditional_rate_limit("10/minute")  # More restrictive for detailed health
async def detailed_health_check(request: Request) -> JSONResponse:
    """Detailed health check endpoint with external service checks."""
    logger.debug("Detailed health check requested")
    health_data = await health_checker.perform_health_check(include_external=True)

    status_code = 200
    if health_data["status"] == "unhealthy":
        status_code = 503
    elif health_data["status"] == "degraded":
        status_code = 200  # Still accepting traffic but with warnings

    return JSONResponse(content=health_data, status_code=status_code)


# Metrics endpoint
@app.get("/metrics", tags=["Monitoring"])
async def metrics() -> JSONResponse:
    """Prometheus metrics endpoint."""
    if not settings.metrics_enabled:
        return JSONResponse(
            content={"error": "Metrics are disabled"},
            status_code=404
        )
    return await metrics_endpoint()


@app.get("/readme", response_class=HTMLResponse, tags=["Documentation"])
async def readme() -> RedirectResponse:
    """Redirect to the PESUAuth GitHub repository."""
    return RedirectResponse("https://github.com/pesu-dev/auth")


@app.post("/authenticate", response_model=ResponseModel, tags=["Authentication"])
@conditional_rate_limit(settings.rate_limit_authenticate)
async def authenticate(request: Request, payload: RequestModel, background_tasks: BackgroundTasks) -> JSONResponse:
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
    logger.info("Authenticating user with PESU Academy", username=username, profile=profile, fields=fields)

    try:
        authentication_result.update(
            await pesu_academy.authenticate(
                username=username,
                password=password,
                profile=profile,
                fields=fields,
            ),
        )

        # Record successful authentication
        record_authentication_attempt(True, username)

        # Prefetch a new client with an unauthenticated CSRF token for the next request
        background_tasks.add_task(_refresh_csrf_token_with_lock)

        # Validate the response
        try:
            authentication_result = ResponseModel.model_validate(authentication_result)
            logger.info("Authentication successful", username=username)
            authentication_result = authentication_result.model_dump(exclude_none=True)
            authentication_result["timestamp"] = current_time.isoformat()
            return JSONResponse(
                status_code=200,
                content=authentication_result,
            )
        except ValidationError as e:
            logger.error("Validation error on ResponseModel", username=username, error=str(e))
            raise PESUAcademyError(
                status_code=500,
                message="Internal Server Error. Please try again later.",
            )

    except Exception as e:
        # Record failed authentication attempt
        record_authentication_attempt(False, username)
        logger.error("Authentication failed", username=username, error=str(e))
        raise


def main() -> None:
    """Main function to run the FastAPI application with command line arguments."""
    # Set up argument parser for command line arguments
    parser = argparse.ArgumentParser(
        description=f"{settings.app_name} - {settings.app_description}",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=settings.host,
        help=f"Host to run the FastAPI application on. Default is {settings.host}",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=settings.port,
        help=f"Port to run the FastAPI application on. Default is {settings.port}",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=settings.debug,
        help="Run the application in debug mode with detailed logging.",
    )
    args = parser.parse_args()

    # Override settings with command line arguments
    if args.debug:
        import os
        os.environ["DEBUG"] = "true"
        os.environ["LOG_FORMAT"] = "console"  # Use console format in debug mode
        # Reconfigure logging for debug mode
        configure_logging()

    logger.info("Starting PESUAuth API",
                host=args.host,
                port=args.port,
                debug=args.debug,
                version=settings.app_version)

    # Run the app
    uvicorn.run(
        "app.app:app",
        host=args.host,
        port=args.port,
        reload=args.debug or settings.reload,
        log_config=None,  # Disable uvicorn's logging config to use our own
    )


if __name__ == "__main__":  # pragma: no cover
    main()  # pragma: no cover
