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

from app.exceptions.base import PESUAcademyError
from app.models import RequestModel, ResponseModel
from app.pesu import PESUAcademy

IST = pytz.timezone("Asia/Kolkata")
REFRESH_INTERVAL_SECONDS = 45 * 60
CSRF_TOKEN_REFRESH_LOCK = asyncio.Lock()


async def _refresh_csrf_token_with_lock() -> None:
    """Refresh the CSRF token with a lock."""
    logging.debug("Refreshing unauthenticated CSRF token...")
    async with CSRF_TOKEN_REFRESH_LOCK:
        await pesu_academy.prefetch_client_with_csrf_token()
        logging.info("Unauthenticated CSRF token refreshed successfully.")


async def _csrf_token_refresh_loop() -> None:
    """Background task to refresh the CSRF token periodically."""
    while True:
        try:
            logging.debug("Refreshing unauthenticated CSRF token...")
            await _refresh_csrf_token_with_lock()
        except Exception:
            logging.exception("Failed to refresh unauthenticated CSRF token in the background.")
        await asyncio.sleep(REFRESH_INTERVAL_SECONDS)


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
    description="A simple API to authenticate PESU credentials using PESU Academy",
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
    responses={
        200: {
            "description": "Successful Health Check.",
            "model": ResponseModel,
            "content": {
                "application/json": {
                    "example": {"status": True, "message": "ok", "timestamp": "2024-07-28T22:30:10.103368+05:30"}
                }
            },
        },
        500: {
            "description": "Internal Server Error.",
            "model": ResponseModel,
            "content": {
                "application/json": {
                    "example": {
                        "status": False,
                        "message": "Internal Server Error. Please try again later.",
                        "timestamp": "2024-07-28T22:30:10.103368+05:30",
                    }
                }
            },
        },
    },
    tags=["Monitoring"],
)
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    logging.debug("Health check requested.")
    return {"status": "ok"}


@app.get(
    "/readme",
    response_class=RedirectResponse,
    status_code=308,
    responses={
        308: {
            "description": "Redirect to the PESUAuth GitHub repository.",
            "content": {
                "text/html": {
                    "example": '<html><head><title>Redirecting...</title></head><body><a href="https://github.com/pesu-dev/auth">Redirect</a></body></html>'
                }
            },
        },
        500: {
            "description": "Internal Server Error.",
            "model": ResponseModel,
            "content": {
                "application/json": {
                    "example": {
                        "status": False,
                        "message": "Internal Server Error. Please try again later.",
                    }
                }
            },
        },
    },
    tags=["Documentation"],
)
async def readme() -> RedirectResponse:
    """Redirect to the PESUAuth GitHub repository."""
    return RedirectResponse("https://github.com/pesu-dev/auth", status_code=308)


@app.post(
    "/authenticate",
    response_model=ResponseModel,
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "basic_srn_auth": {
                            "summary": "Simple Authentication",
                            "description": "Simple authentication using username without requesting profile data",
                            "value": {"username": "PES1201800001", "password": "mySecurePassword123", "profile": False},
                        },
                        "email_auth_with_profile": {
                            "summary": "Authentication with Full Profile",
                            "description": "Authentication using username and requesting all profile fields",
                            "value": {
                                "username": "johndoe@gmail.com",
                                "password": "mySecurePassword123",
                                "profile": True,
                            },
                        },
                        "phone_auth_selective_fields": {
                            "summary": "Authentication with Selected Fields",
                            "description": "Authentication using username and requesting specific profile fields only",
                            "value": {
                                "username": "1234567890",
                                "password": "mySecurePassword123",
                                "profile": True,
                                "fields": ["name", "email", "campus", "branch", "semester"],
                            },
                        },
                    }
                }
            }
        }
    },
    responses={
        200: {
            "description": "Successful Authentication",
            "model": ResponseModel,
            "content": {
                "application/json": {
                    "examples": {
                        "authentication_only": {
                            "summary": "Simple Authentication",
                            "value": {
                                "status": True,
                                "message": "Login successful.",
                                "timestamp": "2024-07-28T22:30:10.103368+05:30",
                            },
                        },
                        "authentication_with_profile": {
                            "summary": "Authentication with Full Profile",
                            "value": {
                                "status": True,
                                "message": "Login successful.",
                                "timestamp": "2024-07-28T22:30:10.103368+05:30",
                                "profile": {
                                    "name": "John Doe",
                                    "prn": "PES1201800001",
                                    "srn": "PES1201800001",
                                    "program": "Bachelor of Technology",
                                    "branch": "Computer Science and Engineering",
                                    "semester": "2",
                                    "section": "C",
                                    "email": "johndoe@gmail.com",
                                    "phone": "1234567890",
                                    "campus_code": 1,
                                    "campus": "RR",
                                },
                            },
                        },
                    }
                }
            },
        },
        400: {
            "description": "Bad Request - Invalid request data",
            "model": ResponseModel,
            "content": {
                "application/json": {
                    "example": {
                        "status": False,
                        "message": "Could not validate request data - body.password: Field required",
                        "timestamp": "2024-07-28T22:30:10.103368+05:30",
                    }
                }
            },
        },
        401: {
            "description": "Unauthorized - Invalid credentials",
            "model": ResponseModel,
            "content": {
                "application/json": {
                    "example": {
                        "status": False,
                        "message": "Invalid username or password, or user does not exist.",
                        "timestamp": "2024-07-28T22:30:10.103368+05:30",
                    }
                }
            },
        },
        422: {
            "description": "Unprocessable entity - Profile parsing error",
            "model": ResponseModel,
            "content": {
                "application/json": {
                    "example": {
                        "status": False,
                        "message": "Failed to parse student profile page from PESU Academy.",
                        "timestamp": "2024-07-28T22:30:10.103368+05:30",
                    }
                }
            },
        },
        500: {
            "description": "Internal Server Error",
            "model": ResponseModel,
            "content": {
                "application/json": {
                    "example": {
                        "status": False,
                        "message": "Internal Server Error. Please try again later.",
                        "timestamp": "2024-07-28T22:30:10.103368+05:30",
                    }
                }
            },
        },
        502: {
            "description": "Bad Gateway - External service error",
            "model": ResponseModel,
            "content": {
                "application/json": {
                    "examples": {
                        "csrf_token_error": {
                            "summary": "CSRF token extraction failed",
                            "value": {
                                "status": False,
                                "message": "CSRF token could not be extracted from the response.",
                                "timestamp": "2024-07-28T22:30:10.103368+05:30",
                            },
                        },
                        "profile_fetch_error": {
                            "summary": "Profile page fetching failed",
                            "value": {
                                "status": False,
                                "message": "Failed to fetch student profile page from PESU Academy.",
                                "timestamp": "2024-07-28T22:30:10.103368+05:30",
                            },
                        },
                    }
                }
            },
        },
    },
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
