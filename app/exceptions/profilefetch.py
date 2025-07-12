"""
Exception class that defines an error raised
when profile data could not be fetched from PESUAcademy
"""

from app.exceptions.base import PESUAuthError


class ProfileFetchError(PESUAuthError):
    """Raised when profile data could not be fetched from PESU Academy."""

    def __init__(self, message="Failed to fetch profile page from PESU Academy."):
        super().__init__(message, status_code=502)
