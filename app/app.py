import argparse
import datetime
import json
import logging
import os

import pytz
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.openapi.utils import get_openapi

from app.pesu import PESUAcademy
from pydantic import ValidationError
from app.models import ResponseModel
import app.util as util

IST = pytz.timezone("Asia/Kolkata")
app = FastAPI(
    title="PESU Auth API",
    description="A simple API to authenticate PESU credentials using PESU Academy",
    version="1.0.0",
)
pesu_academy = PESUAcademy()


@app.get("/", response_class=HTMLResponse, tags=["Documentation"])
async def readme():
    """Serve the rendered README.md as HTML."""
    try:
        if "README.html" not in os.listdir():
            logging.info("README.html does not exist. Beginning conversion...")
            util.convert_readme_to_html()
        logging.info("Rendering README.html...")
        with open("README.html") as f:
            output = f.read()
            return HTMLResponse(content=output)
    except Exception:
        logging.exception("Error rendering home page.")
        return Response(
            content="Error occurred while retrieving home page", status_code=500
        )


@app.post("/", tags=["Authentication"])
async def authenticate(request: Request):
    """
    Authenticate a user with their PESU credentials using PESU Academy.

    Request body should contain:
    - username: str - The user's SRN, PRN, email, or phone number
    - password: str - The user's password
    - profile: bool (optional) - Whether to fetch user profile
    - fields: List[str] (optional) - Profile fields to return
    """
    current_time = datetime.datetime.now(IST)
    # Validate the input provided by the user
    try:
        logging.info("Received authentication request. Beginning input validation...")
        body = await request.json()
        validated_data = util.validate_input(body)
        username = validated_data.username
        password = validated_data.password
        profile = validated_data.profile
        fields = validated_data.fields
    except ValidationError as e:
        logging.exception("Could not validate request data.")
        return JSONResponse(
            status_code=400,
            content={
                "status": False,
                "message": f"Could not validate request data: {e}",
                "timestamp": str(current_time),
            },
        )
    except Exception as e:
        logging.exception("Unexpected error during input validation.")
        return JSONResponse(
            status_code=500,
            content={
                "status": False,
                "message": f"Unexpected error during input validation: {e}",
                "timestamp": str(current_time),
            },
        )

    # Authenticate the user
    try:
        authentication_result = {"timestamp": str(current_time)}
        logging.info(f"Authenticating user={username} with PESU Academy...")
        authentication_result.update(
            pesu_academy.authenticate(
                username=username, password=password, profile=profile, fields=fields
            )
        )
        authentication_result = ResponseModel.model_validate(authentication_result)
        logging.info(
            f"Returning auth result for user={username}: {authentication_result}"
        )
        return JSONResponse(
            content=json.loads(
                authentication_result.model_dump_json(exclude_none=True)
            ),
            status_code=200,
        )
    except Exception as e:
        logging.exception(f"Error authenticating user={username}.")
        return JSONResponse(
            status_code=500,
            content={"status": False, "message": f"Error authenticating user: {e}"},
        )


@app.post("/authenticate", tags=["Authentication"])
async def authenticate_old(request: Request):
    """
    Authenticate a user with their PESU credentials using PESU Academy. Added for backwards compatibility.

    Request body should contain:
    - username: str - The user's SRN, PRN, email, or phone number
    - password: str - The user's password
    - profile: bool (optional) - Whether to fetch user profile
    - fields: List[str] (optional) - Profile fields to return
    """
    current_time = datetime.datetime.now(IST)
    # Validate the input provided by the user
    try:
        logging.info("Received authentication request. Beginning input validation...")
        body = await request.json()
        validated_data = util.validate_input(body)
        username = validated_data.username
        password = validated_data.password
        profile = validated_data.profile
        fields = validated_data.fields
    except ValidationError as e:
        logging.exception("Could not validate request data.")
        return JSONResponse(
            status_code=400,
            content={
                "status": False,
                "message": f"Could not validate request data: {e}",
                "timestamp": str(current_time),
            },
        )
    except Exception as e:
        logging.exception("Unexpected error during input validation.")
        return JSONResponse(
            status_code=500,
            content={
                "status": False,
                "message": f"Unexpected error during input validation: {e}",
                "timestamp": str(current_time),
            },
        )

    # Authenticate the user
    try:
        authentication_result = {"timestamp": str(current_time)}
        logging.info(f"Authenticating user={username} with PESU Academy...")
        authentication_result.update(
            pesu_academy.authenticate(
                username=username, password=password, profile=profile, fields=fields
            )
        )
        authentication_result = ResponseModel.model_validate(authentication_result)
        logging.info(
            f"Returning auth result for user={username}: {authentication_result}"
        )
        return JSONResponse(
            content=json.loads(
                authentication_result.model_dump_json(exclude_none=True)
            ),
            status_code=200,
        )
    except Exception as e:
        logging.exception(f"Error authenticating user={username}.")
        return JSONResponse(
            status_code=500,
            content={"status": False, "message": f"Error authenticating user: {e}"},
        )


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Add schemes
    openapi_schema["schemes"] = ["https", "http"]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi

if __name__ == "__main__":
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

    logging_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=logging_level,
        format="%(asctime)s - %(levelname)s - %(filename)s:%(funcName)s:%(lineno)d - %(message)s",
        filemode="w",
    )

    # Run the app
    import uvicorn

    uvicorn.run("app.app:app", host=args.host, port=args.port, reload=args.debug)
