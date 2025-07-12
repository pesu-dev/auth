class PESUAuthError(Exception):
    """
    Base Class for all PESUAuth errors.
    All exceptions raised by this code will be derived from this base class.
    """

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

    def __str__(self) -> str:
        return self.message
