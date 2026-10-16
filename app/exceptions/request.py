"""Custom exception classes for requests that fail before validation. All errors inherit from PESUAcademyError."""

from app.exceptions.base import PESUAcademyError


class RequestBodyParseError(PESUAcademyError):
    """Raised when the request body cannot be read at all, so it never reaches validation."""

    def __init__(self, message: str = "Could not parse request body.") -> None:
        """Initialize the RequestBodyParseError with a custom message."""
        super().__init__(message, status_code=400)
