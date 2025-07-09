import argparse
import datetime
import json
import logging
import os

import pytz
from flasgger import Swagger
from flask import Flask, request

from app.pesu import PESUAcademy
from pydantic import ValidationError
from app.models import ResponseModel
import app.util as util

IST = pytz.timezone("Asia/Kolkata")
app = Flask(__name__)
pesu_academy = PESUAcademy()


@app.route("/readme")
def readme():
    """
    Serve the rendered README.md as HTML.
    ---
    tags:
      - Documentation
    produces:
      - text/html
    responses:
      200:
        description: Successfully rendered README.md content
      500:
        description: Internal server error while retrieving README.md
    """
    try:
        if "README.html" not in os.listdir():
            logging.info("README.html does not exist. Beginning conversion...")
            util.convert_readme_to_html()
        logging.info("Rendering README.html...")
        with open("README.html") as f:
            output = f.read()
            return output, 200, {"Content-Type": "text/html"}
    except Exception:
        logging.exception("Error rendering home page.")
        return "Error occurred while retrieving home page", 500


@app.route("/authenticate", methods=["POST"])
def authenticate():
    """
    Authenticate a user with their PESU credentials using PESU Academy.
    ---
    tags:
      - Authentication
    consumes:
      - application/json
    produces:
      - application/json
    parameters:
      - in: body
        name: credentials
        required: true
        description: PESU login credentials and optional flags
        schema:
          type: object
          required:
            - username
            - password
          properties:
            username:
              type: string
              description: The user's SRN, PRN, email, or phone number
              example: PES1UG20CS123
            password:
              type: string
              description: The user's password
              example: yourpassword
            profile:
              type: boolean
              description: Whether to fetch the user's profile
              default: false
            fields:
              type: array
              description: List of profile fields to return. Must be from the predefined set of allowed fields.
              items:
                type: string
                enum:
                  - name
                  - prn
                  - srn
                  - program
                  - branch_short_code
                  - branch
                  - semester
                  - section
                  - email
                  - phone
                  - campus_code
                  - campus
              example: ["name", "prn", "branch", "branch_short_code", "campus"]
    responses:
      200:
        description: Authentication successful
        schema:
          type: object
          properties:
            status:
              type: boolean
              example: true
            message:
              type: string
              example: Login successful.
            timestamp:
              type: string
              format: date-time
              example: "2024-07-28 22:30:10.103368+05:30"
            profile:
              type: object
              description: User profile (if profile=true)
              properties:
                name:
                  type: string
                  example: Johnny Blaze
                prn:
                  type: string
                  example: PES1201800001
                srn:
                  type: string
                  example: PES1201800001
                program:
                  type: string
                  example: Bachelor of Technology
                branch_short_code:
                  type: string
                  example: CSE
                branch:
                  type: string
                  example: Computer Science and Engineering
                semester:
                  type: string
                  example: "6"
                section:
                  type: string
                  example: A
                email:
                  type: string
                  example: johnnyblaze@gmail.com
                phone:
                  type: string
                  example: "1234567890"
                campus_code:
                  type: integer
                  example: 1
                campus:
                  type: string
                  example: RR

      400:
        description: Bad request - Invalid input data
        schema:
          type: object
          properties:
            status:
              type: boolean
              example: false
            message:
              type: string
              example: Could not validate request data
            timestamp:
              type: string
              format: date-time
      500:
        description: Internal server error
        schema:
          type: object
          properties:
            status:
              type: boolean
              example: false
            message:
              type: string
              example: Error authenticating user
    """
    current_time = datetime.datetime.now(IST)
    # Validate the input provided by the user
    try:
        logging.info("Received authentication request. Beginning input validation...")
        validated_data = util.validate_input(request.json)
        username = validated_data.username
        password = validated_data.password
        profile = validated_data.profile
        fields = validated_data.fields
    except ValidationError as e:
        logging.exception("Could not validate request data.")
        return (
            json.dumps(
                {
                    "status": False,
                    "message": f"Could not validate request data: {e}",
                    "timestamp": str(current_time),
                }
            ),
            400,
            {"Content-Type": "application/json"},
        )
    except Exception as e:
        logging.exception("Unexpected error during input validation.")
        return (
            json.dumps(
                {
                    "status": False,
                    "message": f"Unexpected error during input validation: {e}",
                    "timestamp": str(current_time),
                }
            ),
            500,
            {"Content-Type": "application/json"},
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
        return (
            authentication_result.model_dump_json(exclude_none=True, indent=4),
            200,
            {"Content-Type": "application/json"},
        )
    except Exception as e:
        logging.exception(f"Error authenticating user={username}.")
        return (
            json.dumps({"status": False, "message": f"Error authenticating user: {e}"}),
            500,
            {"Content-Type": "application/json"},
        )


if __name__ == "__main__":
    # Set up argument parser for command line arguments
    parser = argparse.ArgumentParser(
        description="PESUAuth API - A simple API to authenticate PESU credentials using PESU Academy."
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to run the Flask application on. Default is 0.0.0.0",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port to run the Flask application on. Default is 5000",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Run the application in debug mode with detailed logging.",
    )
    args = parser.parse_args()

    swagger_config = {
        "headers": [],
        "specs": [
            {
                "endpoint": "v1",
                "route": "/v1.json",
                "rule_filter": lambda rule: True,
                "model_filter": lambda tag: True,
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/",
    }
    # TODO: Add version to the API
    # TODO: Set host dynamically based on the machine's IP address or domain name
    swagger_template = {
        "swagger": "2.0",
        "info": {
            "title": "PESU Auth API",
            "description": "A simple API to authenticate PESU credentials using PESU Academy",
            # "version": "1.0.0"
        },
        # "host": "localhost:5000",
        "basePath": "/",
        "schemes": ["https", "http"],
    }
    swagger = Swagger(app, config=swagger_config, template=swagger_template)

    logging_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=logging_level,
        format="%(asctime)s - %(levelname)s - %(filename)s:%(funcName)s:%(lineno)d - %(message)s",
        filemode="w",
    )

    # Run the app
    app.run(host=args.host, port=args.port, debug=args.debug)
