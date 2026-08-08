"""Contract-aligned provider error taxonomy."""


class ProviderError(RuntimeError):
    """Base class for all provider boundary failures."""


class RetryableProviderError(ProviderError):
    """Base class for failures that may be retried by a bounded policy."""


class ProviderConfigurationError(ProviderError, ValueError):
    """Provider settings are missing or invalid."""


class ProviderAuthenticationError(ProviderError):
    """The provider rejected the configured credential."""


class ProviderAuthorizationError(ProviderError):
    """The credential or subscription cannot access the resource."""


class ProviderTimeoutError(RetryableProviderError):
    """A provider request exceeded its connect or read timeout."""


class ProviderNetworkError(RetryableProviderError):
    """A temporary network failure prevented the request."""


class ProviderRateLimitError(RetryableProviderError):
    """The provider rejected a request because a quota was exhausted."""

    def __init__(self, retry_after_seconds: float | None = None) -> None:
        super().__init__("API-Football request was rate limited.")
        self.retry_after_seconds = retry_after_seconds


class ProviderServerError(RetryableProviderError):
    """The provider returned a retryable server failure."""


class ProviderRequestError(ProviderError):
    """The provider rejected a non-retryable request."""


class ProviderResponseSchemaError(ProviderError):
    """The response was malformed or violated the supported schema."""


class UnsupportedProviderValueError(ProviderError):
    """The provider returned an unsupported enum or value."""


class ProviderPaginationError(ProviderError):
    """Pagination metadata was missing, contradictory, or incomplete."""


class ProviderPartialFetchError(ProviderError):
    """A collection fetch failed after one or more pages succeeded."""


class ProviderIntegrityError(ProviderError):
    """Provider identifiers or normalized objects conflicted."""
