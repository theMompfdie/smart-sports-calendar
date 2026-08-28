class OpenLigaDBError(RuntimeError):
    """Base class for secret-safe OpenLigaDB failures."""


class OpenLigaDBConfigurationError(OpenLigaDBError, ValueError):
    """OpenLigaDB configuration is invalid."""


class OpenLigaDBRequestError(OpenLigaDBError):
    """An OpenLigaDB request failed."""


class OpenLigaDBRetryableError(OpenLigaDBRequestError):
    """A transient OpenLigaDB request failed after bounded retries."""


class OpenLigaDBSchemaError(OpenLigaDBError):
    """An OpenLigaDB response does not satisfy the reviewed schema."""


class OpenLigaDBIntegrityError(OpenLigaDBError):
    """An OpenLigaDB snapshot is structurally valid but unsafe to import."""


class OpenLigaDBResolutionError(OpenLigaDBError):
    """OpenLigaDB data cannot be resolved to the canonical catalog."""
