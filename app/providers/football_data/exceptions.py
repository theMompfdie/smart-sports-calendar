class FootballDataError(RuntimeError):
    """Base class for secret-safe football-data.org failures."""


class FootballDataConfigurationError(FootballDataError, ValueError):
    """football-data.org configuration is invalid."""


class FootballDataRequestError(FootballDataError):
    """A provider request failed without exposing request secrets."""


class FootballDataRetryableError(FootballDataRequestError):
    """A transient provider request failed after bounded retries."""


class FootballDataSchemaError(FootballDataError):
    """A provider response does not satisfy the reviewed v4 schema."""


class FootballDataIntegrityError(FootballDataError):
    """A provider snapshot is structurally valid but unsafe to import."""


class FootballDataResolutionError(FootballDataError):
    """Provider data cannot be resolved to the canonical catalog."""
