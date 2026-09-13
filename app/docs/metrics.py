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
pesu_auth_requests_failed_total 182
# HELP pesu_auth_responses_total HTTP responses, by status code.
# TYPE pesu_auth_responses_total counter
pesu_auth_responses_total{status="200"} 1094
# HELP pesu_auth_route_requests_total HTTP requests, by matched route and method.
# TYPE pesu_auth_route_requests_total counter
pesu_auth_route_requests_total{method="GET",route="/health"} 302
# HELP pesu_auth_errors_total Errors rendered by an exception handler, by exception class.
# TYPE pesu_auth_errors_total counter
pesu_auth_errors_total{type="AuthenticationError"} 160
# HELP pesu_auth_authentication_requests_total Authentication requests, by whether profile data was requested.
# TYPE pesu_auth_authentication_requests_total counter
pesu_auth_authentication_requests_total{profile="false"} 640
# HELP pesu_auth_authentication_results_total Authentication attempts, by outcome. errors_total says why one failed.
# TYPE pesu_auth_authentication_results_total counter
pesu_auth_authentication_results_total{result="failure"} 162
# HELP pesu_auth_profile_field_filtering_total Profile fetches, by whether the caller narrowed the fields returned.
# TYPE pesu_auth_profile_field_filtering_total counter
pesu_auth_profile_field_filtering_total{enabled="false"} 94
# HELP pesu_auth_profile_parse_errors_total Profile page parse failures, by what could not be parsed.
# TYPE pesu_auth_profile_parse_errors_total counter
pesu_auth_profile_parse_errors_total{reason="unknown_field"} 3
# HELP pesu_auth_validation_errors_total Request validation failures, by the field that failed.
# TYPE pesu_auth_validation_errors_total counter
pesu_auth_validation_errors_total{field="password"} 4
# HELP pesu_auth_failures_total Failed requests, by whose fault it was: the caller's (4xx) or ours (5xx).
# TYPE pesu_auth_failures_total counter
pesu_auth_failures_total{fault="client"} 172
# HELP pesu_auth_request_latency_seconds Seconds from receiving a request to starting its response.
# TYPE pesu_auth_request_latency_seconds summary
pesu_auth_request_latency_seconds_sum 742.1841932
pesu_auth_request_latency_seconds_count 1284
# HELP pesu_auth_route_latency_seconds Seconds from receiving a request to starting its response, by route.
# TYPE pesu_auth_route_latency_seconds summary
pesu_auth_route_latency_seconds_sum{method="GET",route="/health"} 0.413
pesu_auth_route_latency_seconds_count{method="GET",route="/health"} 302
# HELP pesu_auth_upstream_requests_total Requests made to PESU Academy, by operation and outcome.
# TYPE pesu_auth_upstream_requests_total counter
pesu_auth_upstream_requests_total{operation="csrf_fetch",outcome="error"} 3
# HELP pesu_auth_upstream_responses_total Responses from PESU Academy, by operation and status code.
# TYPE pesu_auth_upstream_responses_total counter
pesu_auth_upstream_responses_total{operation="csrf_fetch",status="200"} 790
# HELP pesu_auth_upstream_latency_seconds Seconds spent waiting on PESU Academy, by operation.
# TYPE pesu_auth_upstream_latency_seconds summary
pesu_auth_upstream_latency_seconds_sum{operation="csrf_fetch"} 210.4
pesu_auth_upstream_latency_seconds_count{operation="csrf_fetch"} 793
# HELP pesu_auth_csrf_cache_total Lookups of the cached unauthenticated CSRF client, by whether the cache was warm.
# TYPE pesu_auth_csrf_cache_total counter
pesu_auth_csrf_cache_total{outcome="hit"} 760
# HELP pesu_auth_csrf_refreshes_total Periodic background refreshes of the unauthenticated CSRF token, by outcome.
# TYPE pesu_auth_csrf_refreshes_total counter
pesu_auth_csrf_refreshes_total{outcome="failure"} 1
# HELP pesu_auth_prefetch_tasks_total Background CSRF prefetch tasks, by outcome.
# TYPE pesu_auth_prefetch_tasks_total counter
pesu_auth_prefetch_tasks_total{outcome="failure"} 4
# HELP pesu_auth_http_clients_total Upstream HTTP client lifecycle. created minus closed is how many are still open.
# TYPE pesu_auth_http_clients_total counter
pesu_auth_http_clients_total{event="closed"} 775
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
    "uptimeSeconds": 0.0,
    "requests": {"total": 1284, "success": 1102, "failed": 182},
    "latency": {"sumSeconds": 742.1841932, "count": 1284, "averageSeconds": 0.5780250725856698},
    "authentication": {"total": 774, "withProfile": 134, "withoutProfile": 640},
    "responsesByStatus": {"200": 1094, "308": 8, "400": 12, "401": 160, "500": 4, "502": 6},
    "requestsByRoute": {
        "GET /health": {
            "requests": 302,
            "latency": {"sumSeconds": 0.413, "count": 302, "averageSeconds": 0.0013675496688741722},
        },
        "POST /authenticate": {
            "requests": 774,
            "latency": {"sumSeconds": 741.2118, "count": 774, "averageSeconds": 0.957637984496124},
        },
    },
    "errorsByType": {"AuthenticationError": 160, "ProfileFetchError": 2, "RequestValidationError": 12},
    "requestsInFlight": 1,
    "failuresByFault": {"client": 172, "server": 10},
    "validationErrorsByField": {"password": 4, "username": 8},
    "authenticationResults": {"failure": 162, "success": 612},
    "profileFieldFiltering": {"false": 94, "true": 40},
    "profileParseErrors": {"unknown_field": 3},
    "upstream": {
        "csrf_fetch": {
            "success": 790,
            "error": 3,
            "cancelled": 0,
            "latency": {"sumSeconds": 210.4, "count": 793, "averageSeconds": 0.26532156368221943},
            "responsesByStatus": {"200": 790},
        },
        "login": {
            "success": 774,
            "error": 2,
            "cancelled": 1,
            "latency": {"sumSeconds": 620.4, "count": 776, "averageSeconds": 0.7994845360824742},
            "responsesByStatus": {"200": 774},
        },
        "profile_fetch": {
            "success": 134,
            "error": 1,
            "cancelled": 0,
            "latency": {"sumSeconds": 190.2, "count": 135, "averageSeconds": 1.4088888888888889},
            "responsesByStatus": {"200": 134},
        },
    },
    "csrfCache": {"hit": 760, "miss": 14},
    "csrfRefreshes": {"failure": 1, "success": 45},
    "prefetchTasks": {"failure": 4, "success": 770},
    "httpClients": {"closed": 775, "created": 776},
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
