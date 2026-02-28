"""Custom exception hierarchy for application errors."""


class AppError(Exception):
    """Base application error. All custom exceptions inherit from this."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class NotFoundError(AppError):
    """Resource not found error (404)."""

    def __init__(self, resource: str = "Resource") -> None:
        super().__init__(f"{resource} not found", status_code=404)


class ForbiddenError(AppError):
    """Not authorized error (403)."""

    def __init__(self) -> None:
        super().__init__("Not authorized", status_code=403)


class ValidationError(AppError):
    """Validation error (422)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=422)


class AuthenticationError(AppError):
    """Authentication failed (401)."""

    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(message, status_code=401)


class ConflictError(AppError):
    """Resource conflict (409)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=409)


class ServiceUnavailableError(AppError):
    """Service unavailable (503)."""

    def __init__(self, message: str = "Service unavailable") -> None:
        super().__init__(message, status_code=503)
