"""Custom docs for the /metrics PESUAuth endpoint."""

from app.docs.base import ApiDocs

metrics_docs = ApiDocs(
    request_examples={},  # GET endpoint doesn't need request examples
    response_examples={
        200: {
            "description": "Metrics retrieved successfully",
            "content": {
                "application/json": {
                    "examples": {
                        "metrics_response": {
                            "summary": "Current Metrics",
                            "description": "All current application metrics including authentication counts and error rates",
                            "value": {
                                "status": True,
                                "message": "Metrics retrieved successfully",
                                "timestamp": "2025-08-28T15:30:45.123456+05:30",
                                "metrics": {
                                    "auth_success_total": 150,
                                    "auth_failure_total": 12,
                                    "validation_error_total": 8,
                                    "pesu_academy_error_total": 5,
                                    "unhandled_exception_total": 0,
                                    "csrf_token_error_total": 2,
                                    "profile_fetch_error_total": 1,
                                    "profile_parse_error_total": 0,
                                    "csrf_token_refresh_success_total": 45,
                                    "csrf_token_refresh_failure_total": 1,
                                },
                            },
                        }
                    }
                }
            },
        }
    },
)
