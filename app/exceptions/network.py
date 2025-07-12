from app.exceptions.base import PESUAuthError


class NetworkError(PESUAuthError):
    """Raised when there is a network or connectivity issue with PESU Academy."""

    def __init__(self, message="Network issue while connecting to PESU Academy."):
        super().__init__(message, status_code=504)
