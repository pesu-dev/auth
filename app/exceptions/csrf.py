from app.exceptions.base import PESUAuthError


class CSRFTokenError(PESUAuthError):
    """Raised when CSRF token is missing or cannot be extracted."""

    def __init__(self, message: str = "Invalid CSRF Token", status_code: int = 500):
        super().__init__(message, status_code)

    def __str__(self) -> str:
        return super().__str__()
