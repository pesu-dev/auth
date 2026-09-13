"""Custom exception classes for the metrics endpoint. All errors inherit from PESUAcademyError."""

from app.exceptions.base import PESUAcademyError


class MetricsAuthorizationError(PESUAcademyError):
    """Raised when the metrics endpoint is token-protected and the request did not present it."""

    def __init__(self, message: str = "Invalid or missing metrics token.") -> None:
        """Initialize the MetricsAuthorizationError with a custom message."""
        # A 401 is required to say how to authenticate, so a scraper can tell "your credentials
        # are wrong" apart from "this endpoint wants no credentials at all".
        super().__init__(message, status_code=401, headers={"WWW-Authenticate": "Bearer"})
