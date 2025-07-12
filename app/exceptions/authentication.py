from app.exceptions.base import PESUAuthError


class AuthenticationError(PESUAuthError):
    """Raised when authentication with PESU Academy fails.

    Most likely caused by an invalid combination of username and password.
    """

    def __init__(self, message: str = "Invalid username or password", status_code: int = 500):
        super().__init__(message, status_code)

    def __str__(self) -> str:
        return super().__str__()
