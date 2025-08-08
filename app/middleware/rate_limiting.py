"""Rate limiting middleware for PESUAuth API."""

import logging
import os

from fastapi import Request, Response
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


def get_client_ip(request: Request) -> str:
    """Get client IP address, considering X-Forwarded-For header."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain
        return forwarded_for.split(",")[0].strip()
    return get_remote_address(request)


def create_limiter() -> Limiter | None:
    """Create and configure the rate limiter."""
    # Check if rate limiting is enabled
    if os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "false":
        logging.info("Rate limiting is disabled")
        return None

    # Check if Redis is enabled for rate limiting storage
    redis_enabled = os.getenv("REDIS_ENABLED", "true").lower() == "true"
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

    if redis_enabled:
        try:
            # Test Redis connection (but don't connect yet, slowapi will handle that)
            logging.info(f"Configuring Redis for rate limiting: {redis_url}")

            limiter = Limiter(
                key_func=get_client_ip,
                storage_uri=redis_url,
                default_limits=["100/hour"],  # Default limit if not specified
            )
        except Exception as e:
            logging.warning(f"Redis configuration failed, using in-memory rate limiting: {e}")
            # Fallback to in-memory storage
            limiter = Limiter(
                key_func=get_client_ip,
                default_limits=["100/hour"],  # Default limit if not specified
            )
    else:
        logging.info("Using in-memory storage for rate limiting")
        # Use in-memory storage
        limiter = Limiter(
            key_func=get_client_ip,
            default_limits=["100/hour"],  # Default limit if not specified
        )

    return limiter


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Custom rate limit exceeded handler."""
    logging.warning(f"Rate limit exceeded for IP: {get_client_ip(request)}")

    return Response(
        content='{"status": false, "message": "Rate limit exceeded. Please try again later."}',
        status_code=429,
        media_type="application/json",
        headers={
            "X-RateLimit-Limit": str(exc.detail.split()[0]) if exc.detail else "100",
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(exc.retry_after) if exc.retry_after else "3600",
        }
    )


# Create the limiter instance
limiter = create_limiter()
