"""Base exception class for PESUAcademy."""


class PESUAcademyError(Exception):
    """Base class for all PESU Academy-related errors."""

    def __init__(self, message: str, status_code: int) -> None:
        """Initialize the PESUAcademyError with a custom message and status code."""
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

    def __str__(self) -> str:
        """Return a string representation of the error."""
        return f"{self.__class__.__name__}: {self.message}"
