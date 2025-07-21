from app.exceptions.base import PESUAcademyError
# TODO: See if we can rename this file


class AuthenticationError(PESUAcademyError):
    """Raised when authentication with PESU Academy fails."""

    def __init__(self, message="Invalid username or password, or user does not exist."):
        super().__init__(message, status_code=401)


class CSRFTokenError(PESUAcademyError):
    """Raised when CSRF token is missing or cannot be extracted."""

    def __init__(self, message="CSRF token could not be extracted from the response."):
        super().__init__(message, status_code=502)


class ProfileFetchError(PESUAcademyError):
    """Raised when profile data could not be fetched from PESU Academy."""

    def __init__(self, message="Failed to fetch student profile page from PESU Academy."):
        super().__init__(message, status_code=502)


class ProfileParseError(PESUAcademyError):
    """Raised when profile data could not be parsed from PESU Academy."""

    def __init__(self, message="Failed to parse student profile page from PESU Academy."):
        super().__init__(message, status_code=422)
