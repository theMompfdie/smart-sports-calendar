import json
import os
import re
from dataclasses import dataclass, field
from math import isfinite
from pathlib import Path
from urllib.parse import urlsplit

from app.providers.api_football.exceptions import ProviderConfigurationError
from app.providers.contracts import (
    SourceConfigurationError,
    SourceJobDefinition,
    SourceRole,
    SourceScope,
)

INSTANCE_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")


@dataclass(frozen=True)
class ApiFootballSettings:
    enabled: bool
    api_key: str = field(repr=False)
    base_url: str = "https://v3.football.api-sports.io"
    connect_timeout_seconds: float = 5.0
    read_timeout_seconds: float = 30.0
    max_attempts: int = 3
    retry_base_delay_seconds: float = 1.0
    retry_max_delay_seconds: float = 30.0
    import_interval_seconds: int = 3600


@dataclass(frozen=True)
class FootballDataSettings:
    enabled: bool
    api_key: str = field(repr=False)
    base_url: str = "https://api.football-data.org"
    connect_timeout_seconds: float = 5.0
    read_timeout_seconds: float = 30.0
    max_attempts: int = 3
    retry_base_delay_seconds: float = 1.0
    retry_max_delay_seconds: float = 30.0
    minimum_request_interval_seconds: float = 6.1
    requests_per_minute: int = 10


@dataclass(frozen=True)
class OpenLigaDBSettings:
    enabled: bool
    base_url: str = "https://api.openligadb.de"
    connect_timeout_seconds: float = 5.0
    read_timeout_seconds: float = 30.0
    max_attempts: int = 3
    retry_base_delay_seconds: float = 1.0
    retry_max_delay_seconds: float = 30.0
    minimum_request_interval_seconds: float = 1.0


@dataclass(frozen=True)
class OefbIcalSettings:
    enabled: bool
    feed_url: str = field(default="", repr=False)
    connect_timeout_seconds: float = 5.0
    read_timeout_seconds: float = 30.0
    max_attempts: int = 3
    retry_base_delay_seconds: float = 1.0
    retry_max_delay_seconds: float = 30.0
    minimum_poll_interval_seconds: int = 21600


@dataclass(frozen=True)
class Settings:
    database_path: Path
    log_level: str
    heartbeat_interval: int
    m365_tenant_id: str
    m365_client_id: str
    m365_client_secret: str
    m365_user_id: str
    outlook_calendar_name: str
    outlook_calendar_id: str
    synchronization_batch_limit: int
    graph_base_url: str
    graph_startup_validation_enabled: bool
    api_football: ApiFootballSettings = field(
        default_factory=lambda: ApiFootballSettings(
            enabled=False,
            api_key="",
        )
    )
    football_data: FootballDataSettings = field(
        default_factory=lambda: FootballDataSettings(enabled=False, api_key="")
    )
    openligadb: OpenLigaDBSettings = field(
        default_factory=lambda: OpenLigaDBSettings(enabled=False)
    )
    oefb_ical: OefbIcalSettings = field(
        default_factory=lambda: OefbIcalSettings(enabled=False)
    )
    source_jobs: tuple[SourceJobDefinition, ...] = ()
    instance_name: str = "default"


def get_required_environment_variable(name: str) -> str:
    value = os.getenv(name, "").strip()

    if not value:
        raise ValueError(f"{name} must be configured.")

    return value


def get_instance_name() -> str:
    value = os.getenv("INSTANCE_NAME", "default").strip()

    if not INSTANCE_NAME_PATTERN.fullmatch(value):
        raise ValueError(
            "INSTANCE_NAME must start with a lowercase letter or digit and contain "
            "only lowercase letters, digits, hyphens, or underscores (maximum 63 "
            "characters)."
        )

    return value


def get_boolean_environment_variable(
    name: str,
    default: bool,
) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    normalized_value = value.strip().lower()

    if normalized_value in {"1", "true", "yes", "on"}:
        return True

    if normalized_value in {"0", "false", "no", "off"}:
        return False

    raise ValueError(f"{name} must be one of: true, false, 1, 0, yes, no, on, off.")


def get_positive_integer_environment_variable(
    name: str,
    default: int,
) -> int:
    raw_value = os.getenv(name, str(default))

    try:
        value = int(raw_value)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer.") from error

    if value <= 0:
        raise ValueError(f"{name} must be greater than zero.")

    return value


def get_positive_float_environment_variable(
    name: str,
    default: float,
) -> float:
    raw_value = os.getenv(name, str(default))

    try:
        value = float(raw_value)
    except ValueError as error:
        raise ProviderConfigurationError(f"{name} must be a number.") from error

    if not isfinite(value) or value <= 0:
        raise ProviderConfigurationError(f"{name} must be greater than zero.")

    return value


def load_api_football_settings() -> ApiFootballSettings:
    try:
        enabled = get_boolean_environment_variable(
            "API_FOOTBALL_ENABLED",
            default=False,
        )
    except ValueError as error:
        raise ProviderConfigurationError(str(error)) from error
    api_key = os.getenv("API_FOOTBALL_API_KEY", "").strip()

    if enabled and not api_key:
        raise ProviderConfigurationError(
            "API_FOOTBALL_API_KEY must be configured when API_FOOTBALL_ENABLED is true."
        )

    base_url = os.getenv(
        "API_FOOTBALL_BASE_URL",
        "https://v3.football.api-sports.io",
    ).rstrip("/")
    parsed_url = urlsplit(base_url)

    try:
        _ = parsed_url.port
    except ValueError as error:
        raise ProviderConfigurationError(
            "API_FOOTBALL_BASE_URL must be an HTTPS URL with a valid port and "
            "without credentials, query parameters, or fragments."
        ) from error

    if (
        parsed_url.scheme != "https"
        or not parsed_url.hostname
        or parsed_url.username is not None
        or parsed_url.password is not None
        or parsed_url.query
        or parsed_url.fragment
    ):
        raise ProviderConfigurationError(
            "API_FOOTBALL_BASE_URL must be an HTTPS URL without credentials, "
            "query parameters, or fragments."
        )

    try:
        max_attempts = get_positive_integer_environment_variable(
            "API_FOOTBALL_MAX_ATTEMPTS",
            default=3,
        )
    except ValueError as error:
        raise ProviderConfigurationError(str(error)) from error
    if max_attempts > 10:
        raise ProviderConfigurationError(
            "API_FOOTBALL_MAX_ATTEMPTS must not exceed 10."
        )

    retry_base_delay_seconds = get_positive_float_environment_variable(
        "API_FOOTBALL_RETRY_BASE_DELAY_SECONDS",
        default=1.0,
    )
    retry_max_delay_seconds = get_positive_float_environment_variable(
        "API_FOOTBALL_RETRY_MAX_DELAY_SECONDS",
        default=30.0,
    )
    if retry_max_delay_seconds < retry_base_delay_seconds:
        raise ProviderConfigurationError(
            "API_FOOTBALL_RETRY_MAX_DELAY_SECONDS must be greater than or "
            "equal to API_FOOTBALL_RETRY_BASE_DELAY_SECONDS."
        )
    try:
        import_interval_seconds = get_positive_integer_environment_variable(
            "API_FOOTBALL_IMPORT_INTERVAL_SECONDS",
            default=3600,
        )
    except ValueError as error:
        raise ProviderConfigurationError(str(error)) from error

    return ApiFootballSettings(
        enabled=enabled,
        api_key=api_key,
        base_url=base_url,
        connect_timeout_seconds=get_positive_float_environment_variable(
            "API_FOOTBALL_CONNECT_TIMEOUT_SECONDS",
            default=5.0,
        ),
        read_timeout_seconds=get_positive_float_environment_variable(
            "API_FOOTBALL_READ_TIMEOUT_SECONDS",
            default=30.0,
        ),
        max_attempts=max_attempts,
        retry_base_delay_seconds=retry_base_delay_seconds,
        retry_max_delay_seconds=retry_max_delay_seconds,
        import_interval_seconds=import_interval_seconds,
    )


def load_football_data_settings() -> FootballDataSettings:
    try:
        enabled = get_boolean_environment_variable(
            "FOOTBALL_DATA_ENABLED", default=False
        )
    except ValueError as error:
        raise ProviderConfigurationError(str(error)) from error
    api_key = os.getenv("FOOTBALL_DATA_API_KEY", "").strip()
    if enabled and not api_key:
        raise ProviderConfigurationError(
            "FOOTBALL_DATA_API_KEY must be configured when "
            "FOOTBALL_DATA_ENABLED is true."
        )
    base_url = os.getenv(
        "FOOTBALL_DATA_BASE_URL", "https://api.football-data.org"
    ).rstrip("/")
    parsed_url = urlsplit(base_url)
    try:
        _ = parsed_url.port
    except ValueError as error:
        raise ProviderConfigurationError(
            "FOOTBALL_DATA_BASE_URL must be an HTTPS URL with a valid port."
        ) from error
    if (
        parsed_url.scheme != "https"
        or not parsed_url.hostname
        or parsed_url.username is not None
        or parsed_url.password is not None
        or parsed_url.query
        or parsed_url.fragment
    ):
        raise ProviderConfigurationError(
            "FOOTBALL_DATA_BASE_URL must be an HTTPS URL without credentials, "
            "query parameters, or fragments."
        )
    try:
        max_attempts = get_positive_integer_environment_variable(
            "FOOTBALL_DATA_MAX_ATTEMPTS", default=3
        )
        requests_per_minute = get_positive_integer_environment_variable(
            "FOOTBALL_DATA_REQUESTS_PER_MINUTE", default=10
        )
    except ValueError as error:
        raise ProviderConfigurationError(str(error)) from error
    if max_attempts > 10:
        raise ProviderConfigurationError(
            "FOOTBALL_DATA_MAX_ATTEMPTS must not exceed 10."
        )
    if requests_per_minute > 10:
        raise ProviderConfigurationError(
            "FOOTBALL_DATA_REQUESTS_PER_MINUTE must not exceed the approved "
            "plan limit of 10."
        )
    retry_base = get_positive_float_environment_variable(
        "FOOTBALL_DATA_RETRY_BASE_DELAY_SECONDS", default=1.0
    )
    retry_max = get_positive_float_environment_variable(
        "FOOTBALL_DATA_RETRY_MAX_DELAY_SECONDS", default=30.0
    )
    if retry_max < retry_base:
        raise ProviderConfigurationError(
            "FOOTBALL_DATA_RETRY_MAX_DELAY_SECONDS must be greater than or "
            "equal to FOOTBALL_DATA_RETRY_BASE_DELAY_SECONDS."
        )
    minimum_interval = get_positive_float_environment_variable(
        "FOOTBALL_DATA_MINIMUM_REQUEST_INTERVAL_SECONDS", default=6.1
    )
    required_interval = 60.0 / requests_per_minute
    if minimum_interval < required_interval:
        raise ProviderConfigurationError(
            "FOOTBALL_DATA_MINIMUM_REQUEST_INTERVAL_SECONDS must enforce the "
            "configured requests-per-minute limit."
        )
    return FootballDataSettings(
        enabled=enabled,
        api_key=api_key,
        base_url=base_url,
        connect_timeout_seconds=get_positive_float_environment_variable(
            "FOOTBALL_DATA_CONNECT_TIMEOUT_SECONDS", default=5.0
        ),
        read_timeout_seconds=get_positive_float_environment_variable(
            "FOOTBALL_DATA_READ_TIMEOUT_SECONDS", default=30.0
        ),
        max_attempts=max_attempts,
        retry_base_delay_seconds=retry_base,
        retry_max_delay_seconds=retry_max,
        minimum_request_interval_seconds=minimum_interval,
        requests_per_minute=requests_per_minute,
    )


def load_openligadb_settings() -> OpenLigaDBSettings:
    try:
        enabled = get_boolean_environment_variable("OPENLIGADB_ENABLED", default=False)
    except ValueError as error:
        raise ProviderConfigurationError(str(error)) from error
    base_url = os.getenv("OPENLIGADB_BASE_URL", "https://api.openligadb.de").rstrip("/")
    parsed_url = urlsplit(base_url)
    try:
        _ = parsed_url.port
    except ValueError as error:
        raise ProviderConfigurationError(
            "OPENLIGADB_BASE_URL must be an HTTPS URL with a valid port."
        ) from error
    if (
        parsed_url.scheme != "https"
        or not parsed_url.hostname
        or parsed_url.username is not None
        or parsed_url.password is not None
        or parsed_url.query
        or parsed_url.fragment
    ):
        raise ProviderConfigurationError(
            "OPENLIGADB_BASE_URL must be an HTTPS URL without credentials, "
            "query parameters, or fragments."
        )
    try:
        max_attempts = get_positive_integer_environment_variable(
            "OPENLIGADB_MAX_ATTEMPTS", default=3
        )
    except ValueError as error:
        raise ProviderConfigurationError(str(error)) from error
    if max_attempts > 10:
        raise ProviderConfigurationError("OPENLIGADB_MAX_ATTEMPTS must not exceed 10.")
    retry_base = get_positive_float_environment_variable(
        "OPENLIGADB_RETRY_BASE_DELAY_SECONDS", default=1.0
    )
    retry_max = get_positive_float_environment_variable(
        "OPENLIGADB_RETRY_MAX_DELAY_SECONDS", default=30.0
    )
    if retry_max < retry_base:
        raise ProviderConfigurationError(
            "OPENLIGADB_RETRY_MAX_DELAY_SECONDS must be greater than or equal "
            "to OPENLIGADB_RETRY_BASE_DELAY_SECONDS."
        )
    return OpenLigaDBSettings(
        enabled=enabled,
        base_url=base_url,
        connect_timeout_seconds=get_positive_float_environment_variable(
            "OPENLIGADB_CONNECT_TIMEOUT_SECONDS", default=5.0
        ),
        read_timeout_seconds=get_positive_float_environment_variable(
            "OPENLIGADB_READ_TIMEOUT_SECONDS", default=30.0
        ),
        max_attempts=max_attempts,
        retry_base_delay_seconds=retry_base,
        retry_max_delay_seconds=retry_max,
        minimum_request_interval_seconds=get_positive_float_environment_variable(
            "OPENLIGADB_MINIMUM_REQUEST_INTERVAL_SECONDS", default=1.0
        ),
    )


def load_oefb_ical_settings() -> OefbIcalSettings:
    try:
        enabled = get_boolean_environment_variable("OEFB_ICAL_ENABLED", default=False)
    except ValueError as error:
        raise ProviderConfigurationError(str(error)) from error
    feed_url = os.getenv("OEFB_ICAL_FEED_URL", "").strip()
    if enabled and not feed_url:
        raise ProviderConfigurationError(
            "OEFB_ICAL_FEED_URL must be configured when OEFB_ICAL_ENABLED is true."
        )
    if feed_url:
        parsed_url = urlsplit(feed_url)
        try:
            _ = parsed_url.port
        except ValueError as error:
            raise ProviderConfigurationError(
                "OEFB_ICAL_FEED_URL must be an approved HTTPS ÖFB URL."
            ) from error
        if (
            parsed_url.scheme != "https"
            or parsed_url.hostname != "www.fussballoesterreich.at"
            or parsed_url.username is not None
            or parsed_url.password is not None
            or parsed_url.query
            or parsed_url.fragment
            or not parsed_url.path
            or parsed_url.path == "/"
        ):
            raise ProviderConfigurationError(
                "OEFB_ICAL_FEED_URL must be an approved HTTPS ÖFB URL without "
                "credentials, query parameters, or fragments."
            )
    try:
        max_attempts = get_positive_integer_environment_variable(
            "OEFB_ICAL_MAX_ATTEMPTS", default=3
        )
        minimum_poll_interval_seconds = get_positive_integer_environment_variable(
            "OEFB_ICAL_MINIMUM_POLL_INTERVAL_SECONDS", default=21600
        )
    except ValueError as error:
        raise ProviderConfigurationError(str(error)) from error
    if max_attempts > 10:
        raise ProviderConfigurationError("OEFB_ICAL_MAX_ATTEMPTS must not exceed 10.")
    if minimum_poll_interval_seconds < 21600:
        raise ProviderConfigurationError(
            "OEFB_ICAL_MINIMUM_POLL_INTERVAL_SECONDS must be at least 21600."
        )
    retry_base = get_positive_float_environment_variable(
        "OEFB_ICAL_RETRY_BASE_DELAY_SECONDS", default=1.0
    )
    retry_max = get_positive_float_environment_variable(
        "OEFB_ICAL_RETRY_MAX_DELAY_SECONDS", default=30.0
    )
    if retry_max < retry_base:
        raise ProviderConfigurationError(
            "OEFB_ICAL_RETRY_MAX_DELAY_SECONDS must be greater than or equal "
            "to OEFB_ICAL_RETRY_BASE_DELAY_SECONDS."
        )
    return OefbIcalSettings(
        enabled=enabled,
        feed_url=feed_url,
        connect_timeout_seconds=get_positive_float_environment_variable(
            "OEFB_ICAL_CONNECT_TIMEOUT_SECONDS", default=5.0
        ),
        read_timeout_seconds=get_positive_float_environment_variable(
            "OEFB_ICAL_READ_TIMEOUT_SECONDS", default=30.0
        ),
        max_attempts=max_attempts,
        retry_base_delay_seconds=retry_base,
        retry_max_delay_seconds=retry_max,
        minimum_poll_interval_seconds=minimum_poll_interval_seconds,
    )


def load_source_jobs() -> tuple[SourceJobDefinition, ...]:
    raw_value = os.getenv("SOURCE_JOBS_JSON", "[]").strip()
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError as error:
        raise SourceConfigurationError(
            "SOURCE_JOBS_JSON must be valid JSON."
        ) from error
    if not isinstance(payload, list):
        raise SourceConfigurationError("SOURCE_JOBS_JSON must be a JSON array.")

    jobs: list[SourceJobDefinition] = []
    for index, raw_job in enumerate(payload):
        if not isinstance(raw_job, dict):
            raise SourceConfigurationError(
                f"SOURCE_JOBS_JSON item {index} must be an object."
            )
        required = {
            "job_key",
            "source_key",
            "sport_key",
            "competition_key",
            "season_key",
            "role",
            "interval_seconds",
        }
        if set(raw_job) != required:
            raise SourceConfigurationError(
                f"SOURCE_JOBS_JSON item {index} must contain exactly: "
                + ", ".join(sorted(required))
                + "."
            )
        text_fields: dict[str, str] = {}
        for name in required - {"interval_seconds"}:
            value = raw_job[name]
            if not isinstance(value, str) or not value.strip():
                raise SourceConfigurationError(
                    f"SOURCE_JOBS_JSON item {index} field {name} must be a "
                    "non-empty string."
                )
            text_fields[name] = value.strip()
        for name in (
            "job_key",
            "source_key",
            "sport_key",
            "competition_key",
            "season_key",
        ):
            if not INSTANCE_NAME_PATTERN.fullmatch(text_fields[name]):
                raise SourceConfigurationError(
                    f"SOURCE_JOBS_JSON item {index} field {name} must use only "
                    "lowercase letters, digits, hyphens, or underscores and "
                    "must not exceed 63 characters."
                )
        try:
            role = SourceRole(text_fields["role"])
        except ValueError as error:
            raise SourceConfigurationError(
                f"SOURCE_JOBS_JSON item {index} has an unsupported role."
            ) from error
        interval_seconds = raw_job["interval_seconds"]
        if (
            isinstance(interval_seconds, bool)
            or not isinstance(interval_seconds, int)
            or interval_seconds <= 0
        ):
            raise SourceConfigurationError(
                f"SOURCE_JOBS_JSON item {index} interval_seconds must be a "
                "positive integer."
            )
        jobs.append(
            SourceJobDefinition(
                job_key=text_fields["job_key"],
                source_key=text_fields["source_key"],
                role=role,
                scope=SourceScope(
                    sport_key=text_fields["sport_key"],
                    competition_key=text_fields["competition_key"],
                    season_key=text_fields["season_key"],
                ),
                interval_seconds=interval_seconds,
            )
        )
    validate_source_jobs(jobs)
    return tuple(jobs)


def validate_source_jobs(jobs: list[SourceJobDefinition]) -> None:
    job_keys = [job.job_key for job in jobs]
    if len(job_keys) != len(set(job_keys)):
        raise SourceConfigurationError(
            "SOURCE_JOBS_JSON job_key values must be unique."
        )

    active_by_scope: dict[SourceScope, list[SourceJobDefinition]] = {}
    seen_source_scopes: set[tuple[str, SourceScope]] = set()
    for job in jobs:
        if not job.enabled:
            continue
        source_scope = (job.source_key, job.scope)
        if source_scope in seen_source_scopes:
            raise SourceConfigurationError(
                "A source may have only one active job per competition and season."
            )
        seen_source_scopes.add(source_scope)
        active_by_scope.setdefault(job.scope, []).append(job)

    for scope, scoped_jobs in active_by_scope.items():
        authorities = [
            job for job in scoped_jobs if job.role is SourceRole.AUTHORITATIVE
        ]
        if len(authorities) != 1:
            raise SourceConfigurationError(
                "Each active competition and season scope must have exactly one "
                f"authoritative source: {scope.sport_key}/"
                f"{scope.competition_key}/{scope.season_key}."
            )


def load_settings() -> Settings:
    return Settings(
        instance_name=get_instance_name(),
        database_path=Path(
            os.getenv(
                "DATABASE_PATH",
                "/data/sports.db",
            )
        ),
        log_level=os.getenv(
            "LOG_LEVEL",
            "INFO",
        ).upper(),
        heartbeat_interval=get_positive_integer_environment_variable(
            "HEARTBEAT_INTERVAL",
            default=300,
        ),
        m365_tenant_id=get_required_environment_variable("M365_TENANT_ID"),
        m365_client_id=get_required_environment_variable("M365_CLIENT_ID"),
        m365_client_secret=get_required_environment_variable("M365_CLIENT_SECRET"),
        m365_user_id=get_required_environment_variable("M365_USER_ID"),
        outlook_calendar_name=os.getenv(
            "OUTLOOK_CALENDAR_NAME",
            "SMART Sports Calendar",
        ).strip(),
        outlook_calendar_id=get_required_environment_variable("OUTLOOK_CALENDAR_ID"),
        synchronization_batch_limit=(
            get_positive_integer_environment_variable(
                "SYNCHRONIZATION_BATCH_LIMIT",
                default=100,
            )
        ),
        graph_base_url=os.getenv(
            "GRAPH_BASE_URL",
            "https://graph.microsoft.com/v1.0",
        ).rstrip("/"),
        graph_startup_validation_enabled=(
            get_boolean_environment_variable(
                "GRAPH_STARTUP_VALIDATION_ENABLED",
                default=True,
            )
        ),
        api_football=load_api_football_settings(),
        football_data=load_football_data_settings(),
        openligadb=load_openligadb_settings(),
        oefb_ical=load_oefb_ical_settings(),
        source_jobs=load_source_jobs(),
    )
