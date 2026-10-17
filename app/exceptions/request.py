"""Custom exception classes for requests that fail before validation. All errors inherit from PESUAcademyError."""

from app.exceptions.base import PESUAcademyError


class RequestBodyParseError(PESUAcademyError):
    """Raised when the request body cannot be read at all, so it never reaches validation."""

    def __init__(self, message: str = "Could not parse request body.") -> None:
        """Initialize the RequestBodyParseError with a custom message."""
        super().__init__(message, status_code=400)


class RouteNotFoundError(PESUAcademyError):
    """Raised when no route serves the requested path."""

    def __init__(self, message: str = "No route matches this path.") -> None:
        """Initialize the RouteNotFoundError with a custom message."""
        super().__init__(message, status_code=404)


class MethodNotAllowedError(PESUAcademyError):
    """Raised when the path is served, but not for the requested method."""

    def __init__(self, allow: str, message: str = "This method is not allowed on this path.") -> None:
        """Initialize the MethodNotAllowedError.

        Args:
            allow (str): The methods the path is served for, comma separated, for the Allow header a 405
                is required to carry.
            message (str): What the caller is told.
        """
        super().__init__(message, status_code=405, headers={"Allow": allow})
