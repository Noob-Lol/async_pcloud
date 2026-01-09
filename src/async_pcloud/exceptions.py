class ApiError(Exception):
    """Base class for PCloud API exceptions."""


class NoSessionError(ApiError):
    """Raised when the session is not created."""
    def __init__(self):
        msg = "Not connected to PCloud API, call connect(), use 'async with' or set a session."
        super().__init__(msg)


class NoTokenError(ApiError):
    """Raised when the token is missing."""
    def __init__(self):
        super().__init__("PCloud token is missing.")
