"""Monitoring and metrics collection for PESUAuth API."""

import time

from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Prometheus metrics
REQUEST_COUNT = Counter(
    "pesu_auth_requests_total",
    "Total number of requests",
    ["method", "endpoint", "status_code"]
)

REQUEST_DURATION = Histogram(
    "pesu_auth_request_duration_seconds",
    "Request duration in seconds",
    ["method", "endpoint"]
)

AUTHENTICATION_ATTEMPTS = Counter(
    "pesu_auth_authentication_attempts_total",
    "Total number of authentication attempts",
    ["status", "username_type"]  # success/failure, email/prn/phone
)

CSRF_TOKEN_OPERATIONS = Counter(
    "pesu_auth_csrf_operations_total",
    "CSRF token operations",
    ["operation"]  # fetch/refresh/cache_hit/cache_miss
)

ACTIVE_CONNECTIONS = Gauge(
    "pesu_auth_active_connections",
    "Number of active HTTP connections"
)

PESU_ACADEMY_REQUESTS = Counter(
    "pesu_auth_pesu_academy_requests_total",
    "Requests made to PESU Academy",
    ["endpoint", "status_code"]
)

PROFILE_FETCH_DURATION = Histogram(
    "pesu_auth_profile_fetch_duration_seconds",
    "Time taken to fetch profile information",
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float("inf"))
)


class MetricsMiddleware:
    """Middleware to collect request metrics."""

    def __init__(self, app: ASGIApp) -> None:
        """Initialize metrics middleware."""
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process ASGI request with metrics collection."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()

        # Track active connections
        ACTIVE_CONNECTIONS.inc()

        try:
            # Process the request
            response_data = {"status_code": 500}

            async def send_wrapper(message: Message) -> None:
                if message["type"] == "http.response.start":
                    response_data["status_code"] = message["status"]
                await send(message)

            await self.app(scope, receive, send_wrapper)

        finally:
            # Record metrics
            duration = time.time() - start_time
            method = scope.get("method", "")
            path = scope.get("path", "")
            status_code = str(response_data.get("status_code", 500))

            REQUEST_COUNT.labels(
                method=method,
                endpoint=path,
                status_code=status_code
            ).inc()

            REQUEST_DURATION.labels(
                method=method,
                endpoint=path
            ).observe(duration)

            ACTIVE_CONNECTIONS.dec()


def record_authentication_attempt(success: bool, username: str) -> None:
    """Record authentication attempt metrics."""
    status = "success" if success else "failure"
    username_type = detect_username_type(username)

    AUTHENTICATION_ATTEMPTS.labels(
        status=status,
        username_type=username_type
    ).inc()


def detect_username_type(username: str) -> str:
    """Detect the type of username (email, prn, phone)."""
    if "@" in username:
        return "email"
    if username.startswith("PES"):
        return "prn"
    if username.isdigit() and len(username) == 10:
        return "phone"
    return "unknown"


def record_csrf_operation(operation: str) -> None:
    """Record CSRF token operation metrics."""
    CSRF_TOKEN_OPERATIONS.labels(operation=operation).inc()


def record_pesu_academy_request(endpoint: str, status_code: int) -> None:
    """Record requests made to PESU Academy."""
    PESU_ACADEMY_REQUESTS.labels(
        endpoint=endpoint,
        status_code=str(status_code)
    ).inc()


async def metrics_endpoint() -> PlainTextResponse:
    """Prometheus metrics endpoint."""
    return PlainTextResponse(
        generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
