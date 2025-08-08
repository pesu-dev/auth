"""Enhanced logging configuration for PESUAuth API."""

import logging
import os
import sys

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from structlog.stdlib import filter_by_level


def configure_logging() -> None:
    """Configure structured logging for the application."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = os.getenv("LOG_FORMAT", "json")  # json or console

    # Configure structlog
    timestamper = structlog.processors.TimeStamper(fmt="ISO")
    shared_processors = [
        filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if log_format.lower() == "json":
        # JSON format for production
        structlog.configure(
            processors=shared_processors + [
                structlog.processors.JSONRenderer()
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
    else:
        # Console format for development
        structlog.configure(
            processors=shared_processors + [
                structlog.dev.ConsoleRenderer(colors=True)
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level, logging.INFO),
    )

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


class LoggingMiddleware:
    """Middleware for request/response logging."""

    def __init__(self, app: ASGIApp) -> None:
        """Initialize logging middleware."""
        self.app = app
        self.logger = get_logger("middleware.logging")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process ASGI request with logging."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract request information
        method = scope.get("method", "")
        path = scope.get("path", "")
        query_string = scope.get("query_string", b"").decode()
        client_host = scope.get("client", ["unknown", None])[0] if scope.get("client") else "unknown"

        # Get request headers for tracing
        headers = dict(scope.get("headers", []))
        request_id = headers.get(b"x-request-id", b"").decode() or None
        user_agent = headers.get(b"user-agent", b"").decode()

        log_context = {
            "method": method,
            "path": path,
            "query_string": query_string,
            "client_ip": client_host,
            "user_agent": user_agent,
            "request_id": request_id,
        }

        self.logger.info("Request started", **log_context)

        # Track response information
        response_data = {"status_code": 500}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                response_data["status_code"] = message["status"]
                response_data["headers"] = dict(message.get("headers", []))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)

            self.logger.info(
                "Request completed",
                status_code=response_data["status_code"],
                **log_context
            )

        except Exception as e:
            self.logger.error(
                "Request failed",
                error=str(e),
                error_type=type(e).__name__,
                **log_context
            )
            raise
