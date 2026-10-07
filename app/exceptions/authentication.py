"""Custom exception classes for various PESU Academy related errors. All errors inherit from PESUAcademyError."""

from app.exceptions.base import PESUAcademyError


class AuthenticationError(PESUAcademyError):
    """Raised when authentication with PESU Academy fails."""

    def __init__(
        self,
        message: str = "Invalid username or password, or user does not exist.",
        *,
        detail: str | None = None,
    ) -> None:
        """Initialize the AuthenticationError with a custom message, and a detail for the log."""
        super().__init__(message, status_code=401, detail=detail)


class UpstreamError(PESUAcademyError):
    """Raised when PESU Academy cannot be reached to log in, or returns an unexpected response to the login."""

    def __init__(
        self,
        message: str = "PESU Academy could not be reached or returned an unexpected response.",
        *,
        detail: str | None = None,
    ) -> None:
        """Initialize the UpstreamError with a custom message, and a detail for the log."""
        super().__init__(message, status_code=502, detail=detail)


class ProfileFetchError(PESUAcademyError):
    """Raised when profile data could not be fetched from PESU Academy."""

    def __init__(
        self,
        message: str = "Failed to fetch the student profile from PESU Academy.",
        *,
        detail: str | None = None,
    ) -> None:
        """Initialize the ProfileFetchError with a custom message, and a detail for the log."""
        super().__init__(message, status_code=502, detail=detail)


class ProfileParseError(PESUAcademyError):
    """Raised when the profile response from PESU Academy does not have the expected shape."""

    def __init__(
        self,
        message: str = "Failed to parse the profile response from PESU Academy.",
        *,
        detail: str | None = None,
    ) -> None:
        """Initialize the ProfileParseError with a custom message, and a detail for the log."""
        super().__init__(message, status_code=422, detail=detail)
