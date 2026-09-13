"""Base exception class for PESUAcademy."""


class PESUAcademyError(Exception):
    """Base class for all PESU Academy-related errors."""

    def __init__(self, message: str, status_code: int, headers: dict[str, str] | None = None) -> None:
        """Initialize the PESUAcademyError with a custom message, status code and response headers."""
        self.message = message
        self.status_code = status_code
        # Only a 401 needs these today, to carry WWW-Authenticate. None for every other error, and
        # JSONResponse accepts None, so the handler passes it through unconditionally.
        self.headers = headers
        super().__init__(self.message)

    def __str__(self) -> str:
        """Return a string representation of the error."""
        return f"{self.__class__.__name__}: {self.message}"
