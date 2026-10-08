"""Base exception class for PESUAcademy."""


class PESUAcademyError(Exception):
    """Base class for all PESU Academy-related errors."""

    def __init__(
        self,
        message: str,
        status_code: int,
        headers: dict[str, str] | None = None,
        detail: str | None = None,
    ) -> None:
        """Initialize the PESUAcademyError.

        Args:
            message (str): What the caller is told, in the response body. Keep it to the documented,
                fixed text: it is part of the API contract.
            status_code (int): The HTTP status of the response.
            headers (dict[str, str] | None): Extra response headers, if any.
            detail (str | None): What the log is told instead: the specifics, such as the username and
                what PESU Academy answered. Never sent to the caller.
        """
        self.message = message
        self.detail = detail
        self.status_code = status_code
        # Only a 401 needs these today, to carry WWW-Authenticate. None for every other error, and
        # JSONResponse accepts None, so the handler passes it through unconditionally.
        self.headers = headers
        super().__init__(self.message)

    def __str__(self) -> str:
        """Return a string representation of the error, with its detail when it has one."""
        return f"{self.__class__.__name__}: {self.detail or self.message}"
