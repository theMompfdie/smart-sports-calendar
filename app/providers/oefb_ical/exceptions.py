class OefbIcalError(RuntimeError):
    """Base class for secret-safe ÖFB iCalendar failures."""


class OefbIcalConfigurationError(OefbIcalError, ValueError):
    """ÖFB iCalendar configuration is invalid."""


class OefbIcalRequestError(OefbIcalError):
    """An ÖFB iCalendar request failed."""


class OefbIcalRetryableError(OefbIcalRequestError):
    """A transient ÖFB iCalendar request failed after bounded retries."""


class OefbIcalSchemaError(OefbIcalError):
    """An ÖFB iCalendar response violates the qualified schema."""


class OefbIcalIntegrityError(OefbIcalError):
    """An ÖFB iCalendar snapshot is structurally valid but unsafe to import."""
