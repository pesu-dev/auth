from app.exceptions.base import PESUAuthError


class AuthenticationError(PESUAuthError):
    """Raised when authentication with PESU Academy fails."""

    def __init__(self, message="Invalid username or password."):
        super().__init__(message, status_code=401)


class CSRFTokenError(PESUAuthError):
    """Raised when CSRF token is missing or cannot be extracted."""

    def __init__(self, message="CSRF token could not be extracted."):
        super().__init__(message, status_code=500)


class ProfileFetchError(PESUAuthError):
    """Raised when profile data could not be fetched from PESU Academy."""

    def __init__(self, message="Failed to fetch profile page from PESU Academy."):
        super().__init__(message, status_code=502)
