"""Custom exception classes for various PESU Academy related errors. All errors inherit from PESUAcademyError."""

from app.exceptions.base import PESUAcademyError


class AuthenticationError(PESUAcademyError):
    """Raised when authentication with PESU Academy fails."""

    def __init__(self, message: str = "Invalid username or password, or user does not exist.") -> None:
        """Initialize the AuthenticationError with a custom message."""
        super().__init__(message, status_code=401)
