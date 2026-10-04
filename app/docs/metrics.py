"""Custom docs for the /metrics PESUAuth endpoint."""

from app.docs.base import ApiDocs
from app.models import ResponseModel

_INTERNAL_SERVER_ERROR = {
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
}

# One sample per family, so every metric is represented without pasting the whole payload into a
# Swagger dropdown. A real response repeats each labelled family once per label set.
_PROMETHEUS_EXAMPLE = """# HELP pesu_auth_requests_total HTTP requests received.
# TYPE pesu_auth_requests_total counter
pesu_auth_requests_total 1284
# HELP pesu_auth_requests_success_total HTTP requests answered with a status below 400.
# TYPE pesu_auth_requests_success_total counter
pesu_auth_requests_success_total 1102
# HELP pesu_auth_requests_failed_total HTTP requests answered with a status of 400 or above.
# TYPE pesu_auth_requests_failed_total counter
pesu_auth_requests_failed_total 181
# HELP pesu_auth_responses_total HTTP responses, by status code.
# TYPE pesu_auth_responses_total counter
pesu_auth_responses_total{status="200"} 1094
# HELP pesu_auth_route_requests_total HTTP requests, by matched route and method.
# TYPE pesu_auth_route_requests_total counter
pesu_auth_route_requests_total{method="GET",route="/"} 8
# HELP pesu_auth_errors_total Errors rendered by an exception handler, by exception class.
# TYPE pesu_auth_errors_total counter
pesu_auth_errors_total{type="AuthenticationError"} 160
# HELP pesu_auth_authentication_requests_total Authentication requests, by whether profile data was requested.
# TYPE pesu_auth_authentication_requests_total counter
pesu_auth_authentication_requests_total{profile="false"} 640
# HELP pesu_auth_authentication_results_total Authentication attempts, by outcome. errors_total says why one failed.
# TYPE pesu_auth_authentication_results_total counter
pesu_auth_authentication_results_total{result="failure"} 169
# HELP pesu_auth_profile_field_filtering_total Profile fetches, by whether the caller narrowed the fields returned.
# TYPE pesu_auth_profile_field_filtering_total counter
pesu_auth_profile_field_filtering_total{enabled="false"} 90
# HELP pesu_auth_profile_parse_errors_total Profile response parse failures, by what could not be parsed or mapped.
# TYPE pesu_auth_profile_parse_errors_total counter
pesu_auth_profile_parse_errors_total{reason="unknown_program"} 3
# HELP pesu_auth_validation_errors_total Request validation failures, by the field that failed.
# TYPE pesu_auth_validation_errors_total counter
pesu_auth_validation_errors_total{field="password"} 4
# HELP pesu_auth_failures_total Failed requests, by whose fault it was: the caller's (4xx) or ours (5xx).
# TYPE pesu_auth_failures_total counter
pesu_auth_failures_total{fault="client"} 172
# HELP pesu_auth_request_latency_seconds Seconds from receiving a request to starting its response.
# TYPE pesu_auth_request_latency_seconds summary
pesu_auth_request_latency_seconds_sum 1651.761
pesu_auth_request_latency_seconds_count 1283
# HELP pesu_auth_route_latency_seconds Seconds from receiving a request to starting its response, by route.
# TYPE pesu_auth_route_latency_seconds summary
pesu_auth_route_latency_seconds_sum{method="GET",route="/"} 0.08
pesu_auth_route_latency_seconds_count{method="GET",route="/"} 8
# HELP pesu_auth_upstream_requests_total Requests made to PESU Academy, by operation and outcome.
# TYPE pesu_auth_upstream_requests_total counter
pesu_auth_upstream_requests_total{operation="login",outcome="error"} 2
# HELP pesu_auth_upstream_responses_total Responses from PESU Academy, by operation and status code.
# TYPE pesu_auth_upstream_responses_total counter
pesu_auth_upstream_responses_total{operation="login",status="200"} 611
# HELP pesu_auth_upstream_latency_seconds Seconds spent waiting on PESU Academy, by operation.
# TYPE pesu_auth_upstream_latency_seconds summary
pesu_auth_upstream_latency_seconds_sum{operation="login"} 1586.7
pesu_auth_upstream_latency_seconds_count{operation="login"} 773
# HELP pesu_auth_http_clients_total Upstream HTTP client lifecycle. created minus closed is how many are still open.
# TYPE pesu_auth_http_clients_total counter
pesu_auth_http_clients_total{event="closed"} 773
# HELP pesu_auth_lifespan_events_total Application lifespan events, by kind.
# TYPE pesu_auth_lifespan_events_total counter
pesu_auth_lifespan_events_total{event="startup"} 1
# HELP pesu_auth_requests_in_flight Requests received but not yet answered.
# TYPE pesu_auth_requests_in_flight gauge
pesu_auth_requests_in_flight 1
# HELP pesu_auth_process_start_time_seconds Start time of the process since the Unix epoch, in seconds.
# TYPE pesu_auth_process_start_time_seconds gauge
pesu_auth_process_start_time_seconds 1757660400.12
"""

_JSON_EXAMPLE = {
    "startTimeSeconds": 1757660400.12,
    "uptimeSeconds": 86400.0,
    "requests": {"total": 1284, "success": 1102, "failed": 181},
    "latency": {"sumSeconds": 1651.761, "count": 1283, "averageSeconds": 1.2874208885424785},
    "authentication": {"total": 774, "withProfile": 134, "withoutProfile": 640},
    "responsesByStatus": {"200": 1094, "308": 8, "400": 12, "401": 160, "500": 4, "502": 5},
    "requestsByRoute": {
        "GET /": {"requests": 8, "latency": {"sumSeconds": 0.08, "count": 8, "averageSeconds": 0.01}},
        "GET /health": {
            "requests": 302,
            "latency": {"sumSeconds": 0.413, "count": 302, "averageSeconds": 0.0013675496688741722},
        },
        "GET /metrics": {"requests": 180, "latency": {"sumSeconds": 0.36, "count": 180, "averageSeconds": 0.002}},
        "GET /readme": {"requests": 8, "latency": {"sumSeconds": 0.008, "count": 8, "averageSeconds": 0.001}},
        "POST /authenticate": {
            "requests": 786,
            "latency": {"sumSeconds": 1650.9, "count": 785, "averageSeconds": 2.1030573248407642},
        },
    },
    "errorsByType": {
        "AuthenticationError": 160,
        "ProfileFetchError": 3,
        "RequestValidationError": 12,
        "RuntimeError": 4,
        "UpstreamError": 2,
    },
    "requestsInFlight": 1,
    "failuresByFault": {"client": 172, "server": 9},
    "validationErrorsByField": {"password": 4, "username": 8},
    "authenticationResults": {"failure": 169, "success": 604},
    "profileFieldFiltering": {"false": 90, "true": 40},
    "profileParseErrors": {"unknown_program": 3},
    "upstream": {
        "login": {
            "success": 771,
            "error": 2,
            "cancelled": 0,
            "latency": {"sumSeconds": 1586.7, "count": 773, "averageSeconds": 2.0526520051746444},
            "responsesByStatus": {"200": 611, "401": 160},
        },
        "profile_fetch": {
            "success": 132,
            "error": 1,
            "cancelled": 0,
            "latency": {"sumSeconds": 53.2, "count": 133, "averageSeconds": 0.4},
            "responsesByStatus": {"200": 130, "502": 2},
        },
    },
    "httpClients": {"closed": 773, "created": 774},
    "lifespanEvents": {"startup": 1},
}

metrics_docs = ApiDocs(
    request_examples={},
    response_examples={
        200: {
            "description": "The collected metrics, in the format named by `fmt`.",
            "content": {
                "text/plain": {"schema": {"type": "string"}, "example": _PROMETHEUS_EXAMPLE},
                "application/json": {"example": _JSON_EXAMPLE},
            },
        },
        400: {
            "description": "Unrecognised value for `fmt`.",
            "model": ResponseModel,
            "content": {
                "application/json": {
                    "example": {
                        "status": False,
                        "message": (
                            "Could not validate request data - query.fmt: Input should be 'prometheus' or 'json'"
                        ),
                        "timestamp": "2024-07-28T22:30:10.103368+05:30",
                    }
                }
            },
        },
        401: {
            "description": (
                "The server has `METRICS_TOKEN` set and the request did not present it. The "
                "response carries `WWW-Authenticate: Bearer`. While `METRICS_TOKEN` is unset this "
                "cannot occur and the endpoint needs no credentials."
            ),
            "model": ResponseModel,
            "content": {
                "application/json": {
                    "example": {
                        "status": False,
                        "message": "Invalid or missing metrics token.",
                        "timestamp": "2024-07-28T22:30:10.103368+05:30",
                    }
                }
            },
        },
        500: _INTERNAL_SERVER_ERROR,
    },
)
