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
                            "value": {"username": "PES1UG20CS001", "password": "mySecurePassword123", "profile": False},
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
                                    "prn": "PES1202000001",
                                    "srn": "PES1UG20CS001",
                                    "program": "Bachelor of Technology",
                                    "branch": "Computer Science and Engineering",
                                    "semester": "Sem-2",
                                    "section": "Section C",
                                    "email": "johndoe@gmail.com",
                                    "phone": "1234567890",
                                    "campusCode": 1,
                                    "campus": "RR",
                                    "firstName": "John",
                                    "middleName": "Michael",
                                    "lastName": "Doe",
                                    "programShortCode": "B.Tech.",
                                    "branchShortCode": "CSE",
                                    "institute": "PES University (Ring Road)",
                                    "rollNumber": 27,
                                    "gender": "Male",
                                    "dateOfBirth": "2002-01-31",
                                },
                            },
                        },
                        "authentication_with_selected_fields": {
                            "summary": "Authentication with Selected Fields",
                            "value": {
                                "status": True,
                                "message": "Login successful.",
                                "timestamp": "2024-07-28T22:30:10.103368+05:30",
                                "profile": {
                                    "name": "John Doe",
                                    "branch": "Computer Science and Engineering",
                                    "semester": "Sem-2",
                                    "email": "johndoe@gmail.com",
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
            "description": "Unprocessable entity - The profile response from PESU Academy could not be parsed",
            "model": ResponseModel,
            "content": {
                "application/json": {
                    "example": {
                        "status": False,
                        "message": "Failed to parse the profile response from PESU Academy.",
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
                        "upstream_error": {
                            "summary": "Login could not be completed",
                            "value": {
                                "status": False,
                                "message": "PESU Academy could not be reached or returned an unexpected response.",
                                "timestamp": "2024-07-28T22:30:10.103368+05:30",
                            },
                        },
                        "profile_fetch_error": {
                            "summary": "Profile fetching failed",
                            "value": {
                                "status": False,
                                "message": "Failed to fetch the student profile from PESU Academy.",
                                "timestamp": "2024-07-28T22:30:10.103368+05:30",
                            },
                        },
                    }
                }
            },
        },
    },
)
