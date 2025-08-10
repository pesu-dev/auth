"""Custom docs for the /authenticate PESUAuth endpoint."""

from app.docs.base import ApiDocs
from app.models import ResponseModel

authenticate_docs = ApiDocs(
    request_examples={
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
                            "description": "Authentication using username and requesting all profile data",
                            "value": {
                                "username": "johndoe@gmail.com",
                                "password": "mySecurePassword123",
                                "profile": True,
                            },
                        },
                        "phone_auth_selective_fields": {
                            "summary": "Authentication with Selected Fields",
                            "description": "Authentication using username and requesting specific profile data fields",
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
    response_examples={
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
)
