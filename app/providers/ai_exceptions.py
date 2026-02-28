"""AI-specific exception hierarchy.

All exceptions inherit from AppError for consistent error handling.
"""

from app.core.exceptions import AppError


class AIProviderError(AppError):
    """Base exception for all AI provider errors."""

    def __init__(self, provider: str, message: str) -> None:
        self.provider = provider
        super().__init__(message, status_code=503)


class RateLimitError(AIProviderError):
    """Rate limit exceeded error (429)."""

    def __init__(self, provider: str, retry_after: float | None = None) -> None:
        self.retry_after = retry_after
        message = f"Rate limit exceeded for {provider}"
        if retry_after:
            message += f" (retry after {retry_after}s)"
        super().__init__(provider, message)
        self.status_code = 429


class ModelNotAvailableError(AIProviderError):
    """Model not available error."""

    def __init__(self, provider: str, model: str) -> None:
        self.model = model
        super().__init__(provider, f"Model '{model}' not available from {provider}")


class ContextLengthExceededError(AIProviderError):
    """Context length exceeded error."""

    def __init__(self, provider: str, max_tokens: int) -> None:
        self.max_tokens = max_tokens
        super().__init__(
            provider, f"Input exceeds {provider} context limit of {max_tokens} tokens"
        )
        self.status_code = 400
