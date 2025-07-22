import argparse
import datetime
import logging
from pathlib import Path

import pytz
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import ValidationError
from app.pesu import PESUAcademy
from app.models import ResponseModel, RequestModel
import app.util as util

from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request
from app.exceptions.base import PESUAcademyError

IST = pytz.timezone("Asia/Kolkata")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler for startup and shutdown events.
    """
    # Startup
    try:
        logging.info("PESUAuth API startup: Regenerating README.html...")
        util.convert_readme_to_html()
        logging.info("README.html regenerated successfully on startup.")
        # TODO: Cache the README.html file and serve it from the cache if it exists.
        await pesu_academy._prefetch_client_with_csrf_token()
    except Exception:
        logging.exception(
            "Failed to regenerate README.html on startup. Subsequent requests to /readme will attempt to regenerate it."
        )
    yield
    # Shutdown
    if pesu_academy._client:
        await pesu_academy._client.aclose()
    logging.info("PESUAuth API shutdown.")


app = FastAPI(
    title="PESUAuth API",
    description="A simple API to authenticate PESU credentials using PESU Academy",
    version="2.0.0",
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
    logging.info("Health check requested.")
    return {"status": "ok"}


@app.get("/readme", response_class=HTMLResponse, tags=["Documentation"])
async def readme():
    """Serve the rendered README.md as HTML."""
    try:
        if not Path("README.html").exists():
            logging.warning("README.html does not exist. Regenerating...")
            util.convert_readme_to_html()
        logging.info("Serving README.html...")
        # TODO: We should cache the README.html file and serve it from the cache if it exists.
        output = Path("README.html").read_text(encoding="utf-8")
        return HTMLResponse(
            status_code=200,
            content=output,
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except Exception:
        logging.exception("Could not render README.html. Returning an Internal Server Error.")
        raise Exception("Internal Server Error. Please try again later.")


@app.post("/authenticate", response_model=ResponseModel, tags=["Authentication"])
async def authenticate(payload: RequestModel):
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
