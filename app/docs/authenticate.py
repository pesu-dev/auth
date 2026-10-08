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
                            "description": "Authentication with an SRN, without requesting the profile",
                            "value": {"username": "PES1UG20CS001", "password": "mySecurePassword123", "profile": False},
                        },
                        "basic_prn_auth": {
                            "summary": "Authentication with a PRN",
                            "description": "Authentication with a PRN, without requesting the profile",
                            "value": {"username": "PES1202000001", "password": "mySecurePassword123"},
                        },
                        "email_auth_with_profile": {
                            "summary": "Authentication with Full Profile",
                            "description": "Authentication with an email address, requesting every profile field",
                            "value": {
                                "username": "johndoe@gmail.com",
                                "password": "mySecurePassword123",
                                "profile": True,
                            },
                        },
                        "phone_auth_selective_fields": {
                            "summary": "Authentication with Selected Fields",
                            "description": "Authentication with a phone number, requesting only some profile fields",
                            "value": {
                                "username": "1234567890",
                                "password": "mySecurePassword123",
                                "profile": True,
                                "fields": ["name", "email", "campus", "branch", "semester", "firstName", "mobile"],
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
                            "description": (
                                "Every field is always present, and is null when PESU Academy has no value for "
                                "it, does not send it, or sends it in an unexpected shape: for example semester "
                                "and section for a student who has graduated, or middleName for one who has none."
                            ),
                            "value": {
                                "status": True,
                                "message": "Login successful.",
                                "timestamp": "2024-07-28T22:30:10.103368+05:30",
                                "profile": {
                                    "name": "John Doe",
                                    "prn": "PES1202000001",
                                    "srn": "PES1UG20CS001",
                                    "program": "B.Tech.",
                                    "branch": "Computer Science and Engineering",
                                    "semester": "Sem-2",
                                    "section": "Section C",
                                    "email": "johndoe@gmail.com",
                                    "mobile": "1234567890",
                                    "campusCode": 1,
                                    "campus": "PES University (Ring Road)",
                                    "firstName": "John",
                                    "middleName": "Michael",
                                    "lastName": "Doe",
                                    "branchShortCode": "CSE",
                                    "gender": "Male",
                                    "dateOfBirth": "2002-01-31",
                                },
                            },
                        },
                        "authentication_with_profile_graduated": {
                            "summary": "Authentication with Full Profile, Graduated Student",
                            "description": (
                                "A student who has graduated: PESU Academy has no current semester or section for "
                                "them, so those are null, as is middleName for a student with none. For students "
                                "who joined before SRNs existed, srn is the same as prn."
                            ),
                            "value": {
                                "status": True,
                                "message": "Login successful.",
                                "timestamp": "2024-07-28T22:30:10.103368+05:30",
                                "profile": {
                                    "name": "Jane Smith",
                                    "prn": "PES1201800001",
                                    "srn": "PES1201800001",
                                    "program": "B.Tech.",
                                    "branch": "Electronics and Communication Engineering",
                                    "semester": None,
                                    "section": None,
                                    "email": "janesmith@gmail.com",
                                    "mobile": "9876543210",
                                    "campusCode": 1,
                                    "campus": "PES University (Ring Road)",
                                    "firstName": "Jane",
                                    "middleName": None,
                                    "lastName": "Smith",
                                    "branchShortCode": "ECE",
                                    "gender": "Female",
                                    "dateOfBirth": "2000-05-14",
                                },
                            },
                        },
                        "authentication_with_selected_fields": {
                            "summary": "Authentication with Selected Fields",
                            "description": "Only the requested fields, in the order the full profile lists them.",
                            "value": {
                                "status": True,
                                "message": "Login successful.",
                                "timestamp": "2024-07-28T22:30:10.103368+05:30",
                                "profile": {
                                    "name": "John Doe",
                                    "branch": "Computer Science and Engineering",
                                    "semester": "Sem-2",
                                    "email": "johndoe@gmail.com",
                                    "mobile": "1234567890",
                                    "campus": "PES University (Ring Road)",
                                    "firstName": "John",
                                },
                            },
                        },
                    }
                }
            },
        },
        400: {
            "description": (
                "Bad Request - The request body failed validation: a body that is not valid JSON, a missing, empty "
                "or invalid username or password, a value of the wrong type, an unknown key, an unknown profile "
                "field, or an empty fields list. The message names each field that failed and why."
            ),
            "model": ResponseModel,
            "content": {
                "application/json": {
                    "examples": {
                        "missing_field": {
                            "summary": "Missing password",
                            "value": {
                                "status": False,
                                "message": "Could not validate request data - body.password: Field required",
                                "timestamp": "2024-07-28T22:30:10.103368+05:30",
                            },
                        },
                        "empty_username": {
                            "summary": "Empty username",
                            "value": {
                                "status": False,
                                "message": (
                                    "Could not validate request data - body.username: Value error, Username cannot "
                                    "be empty."
                                ),
                                "timestamp": "2024-07-28T22:30:10.103368+05:30",
                            },
                        },
                        "unknown_key": {
                            "summary": "Unknown key in the request body",
                            "value": {
                                "status": False,
                                "message": (
                                    "Could not validate request data - body.extra: Extra inputs are not permitted"
                                ),
                                "timestamp": "2024-07-28T22:30:10.103368+05:30",
                            },
                        },
                        "unknown_profile_field": {
                            "summary": "Unknown profile field",
                            "value": {
                                "status": False,
                                "message": (
                                    "Could not validate request data - body.fields.0: Input should be 'name', "
                                    "'prn', 'srn', 'program', 'branch', 'semester', 'section', 'email', 'mobile', "
                                    "'campusCode', 'campus', 'firstName', 'middleName', 'lastName', "
                                    "'branchShortCode', 'gender' or 'dateOfBirth'"
                                ),
                                "timestamp": "2024-07-28T22:30:10.103368+05:30",
                            },
                        },
                    }
                }
            },
        },
        401: {
            "description": (
                "Unauthorized - PESU Academy rejected the credentials: a wrong password, or a user that does not exist."
            ),
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
            "description": (
                "Unprocessable Entity - PESU Academy's profile response could not be parsed, or reported success "
                "without any STUDENT_INFO, which means their API changed. Only when the profile was requested."
            ),
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
            "description": (
                "Bad Gateway - PESU Academy could not be reached, timed out, or answered the login or profile request "
                "unexpectedly, or declined to serve the profile."
            ),
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
                            "description": (
                                "The login succeeded, but the profile could not be fetched, or PESU Academy declined "
                                "to serve it, as it does for an account that is not a student's."
                            ),
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
