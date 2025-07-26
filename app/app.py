import argparse
import datetime
import logging
import asyncio

import pytz
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import ValidationError
from app.pesu import PESUAcademy
from app.models import ResponseModel, RequestModel
import app.util as util

from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request
from app.exceptions.base import PESUAcademyError

IST = pytz.timezone("Asia/Kolkata")
README_HTML_CACHE: str | None = None
REFRESH_INTERVAL_SECONDS = 45 * 60  # 45 minutes

async def csrf_token_refresh_loop(pesu_academy, shutdown_event: asyncio.Event):
    while not shutdown_event.is_set():
        try:
            await pesu_academy.prefetch_client_with_csrf_token()
            logging.info("Periodic: Refreshed PESUAcademy unauthenticated CSRF token.")
        except Exception:
            logging.exception("Could not refresh CSRF token.")
        try:
            # Wait for the shutdown event or timeout
            logging.debug(f"Waiting for {REFRESH_INTERVAL_SECONDS} seconds before next refresh...")
            await asyncio.wait_for(shutdown_event.wait(), timeout=REFRESH_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            pass

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler for startup and shutdown events.
    """
    # Startup
    # Cache the README.html file
    global README_HTML_CACHE
    try:
        logging.info("PESUAuth API startup")
        logging.debug("Regenerating README.html...")
        README_HTML_CACHE = await util.convert_readme_to_html()
        logging.debug("README.html generated successfully on startup.")
    except Exception:
        logging.exception(
            "Failed to generate README.html on startup. Subsequent requests to /readme will attempt to regenerate it."
        )
    # Prefetch PESUAcademy client for first request
    await pesu_academy.prefetch_client_with_csrf_token()
    logging.info("Prefetched a new PESUAcademy client with an unauthenticated CSRF token.")
    yield

    # Start the periodic CSRF token refresh background task
    shutdown_event = asyncio.Event()
    refresh_task = asyncio.create_task(
        csrf_token_refresh_loop(pesu_academy, shutdown_event)
    )

    # Shutdown
    shutdown_event.set()
    await refresh_task
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
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logging.exception("Request data could not be validated.")
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
async def pesu_exception_handler(request: Request, exc: PESUAcademyError):
    logging.exception(f"PESUAcademyError: {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": False,
            "message": exc.message,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logging.exception("Unhandled exception occurred.")
    return JSONResponse(
        status_code=500,
        content={
            "status": False,
            "message": "Internal Server Error. Please try again later.",
        },
    )


@app.get("/health", tags=["Monitoring"])
async def health_check():
    """
    Health check endpoint to verify if the API is running.
    """
    logging.debug("Health check requested.")
    return {"status": "ok"}


@app.get("/readme", response_class=HTMLResponse, tags=["Documentation"])
async def readme():
    """Serve the rendered README.md as HTML."""
    try:
        global README_HTML_CACHE
        if not README_HTML_CACHE:
            logging.warning("README.html does not exist. Regenerating...")
            README_HTML_CACHE = await util.convert_readme_to_html()
        logging.debug("Serving README.html from cache.")
        return HTMLResponse(
            status_code=200,
            content=README_HTML_CACHE,
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except Exception:
        logging.exception("Could not render README.html. Returning an Internal Server Error.")
        raise Exception("Internal Server Error. Please try again later.")


@app.post("/authenticate", response_model=ResponseModel, tags=["Authentication"])
async def authenticate(payload: RequestModel, background_tasks: BackgroundTasks):
    """
    Authenticate a user using their PESU credentials via the PESU Academy service.

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
            username=username, password=password, profile=profile, fields=fields
        )
    )
    # Prefetch a new client with an unauthenticated CSRF token for the next request
    background_tasks.add_task(pesu_academy.prefetch_client_with_csrf_token)

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
            status_code=500, message="Internal Server Error. Please try again later."
        )


def main():
    """
    Main function to run the FastAPI application with command line arguments.
    """
    # Set up argument parser for command line arguments
    parser = argparse.ArgumentParser(
        description="PESUAuth API - A simple API to authenticate PESU credentials using PESU Academy."
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
