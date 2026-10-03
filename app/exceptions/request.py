"""Errors encountered before request-model validation can run."""

from app.exceptions.base import PESUAcademyError


class RequestBodyParseError(PESUAcademyError):
    """Raised when a request body cannot be decoded for validation."""

    def __init__(self, message: str = "Could not parse request body.") -> None:
        """Initialize a safe parse error without carrying the submitted body."""
        super().__init__(message, status_code=400)
