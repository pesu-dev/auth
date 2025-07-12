from app.exceptions.base import PESUAuthError


class ParsingError(PESUAuthError):
    """Raised when HTML parsing of the PESU Academy response fails."""

    def __init__(self, message="Profile page format is invalid or unsupported."):
        super().__init__(message, status_code=500)
