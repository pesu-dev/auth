"""Custom exceptions for various PESU Academy related errors."""

from app.exceptions.base import PESUAcademyError


class AuthenticationError(PESUAcademyError):
    """Raised when authentication with PESU Academy fails."""

    def __init__(self, message: str = "Invalid username or password, or user does not exist.") -> None:
        """Initialize the AuthenticationError with a custom message."""
        super().__init__(message, status_code=401)


class CSRFTokenError(PESUAcademyError):
    """Raised when CSRF token is missing or cannot be extracted."""

    def __init__(self, message: str = "CSRF token could not be extracted from the response.") -> None:
        """Initialize the CSRFTokenError with a custom message."""
        super().__init__(message, status_code=502)


class ProfileFetchError(PESUAcademyError):
    """Raised when profile data could not be fetched from PESU Academy."""

    def __init__(self, message: str = "Failed to fetch student profile page from PESU Academy.") -> None:
        """Initialize the ProfileFetchError with a custom message."""
        super().__init__(message, status_code=502)


class ProfileParseError(PESUAcademyError):
    """Raised when profile data could not be parsed from PESU Academy."""

    def __init__(self, message: str = "Failed to parse student profile page from PESU Academy.") -> None:
        """Initialize the ProfileParseError with a custom message."""
        super().__init__(message, status_code=422)
