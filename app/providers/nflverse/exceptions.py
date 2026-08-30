class NflverseError(RuntimeError):
    """Base class for secret-safe nflverse failures."""


class NflverseRequestError(NflverseError):
    """An nflverse request failed."""


class NflverseRetryableError(NflverseRequestError):
    """A transient nflverse request failed after bounded retries."""


class NflverseSchemaError(NflverseError):
    """An nflverse response does not satisfy the reviewed CSV schema."""


class NflverseIntegrityError(NflverseError):
    """An nflverse snapshot is structurally valid but unsafe to import."""
