from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from app.providers.api_football.exceptions import (
    ProviderIntegrityError,
    ProviderResponseSchemaError,
    UnsupportedProviderValueError,
)


class ProviderFixtureStatus(Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    FINISHED = "finished"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"
    SUSPENDED = "suspended"
    ABANDONED = "abandoned"
    NOT_PLAYED = "not_played"


STATUS_MAPPING = {
    "TBD": ProviderFixtureStatus.SCHEDULED,
    "NS": ProviderFixtureStatus.SCHEDULED,
    "1H": ProviderFixtureStatus.LIVE,
    "HT": ProviderFixtureStatus.LIVE,
    "2H": ProviderFixtureStatus.LIVE,
    "ET": ProviderFixtureStatus.LIVE,
    "BT": ProviderFixtureStatus.LIVE,
    "P": ProviderFixtureStatus.LIVE,
    "INT": ProviderFixtureStatus.LIVE,
    "LIVE": ProviderFixtureStatus.LIVE,
    "FT": ProviderFixtureStatus.FINISHED,
    "AET": ProviderFixtureStatus.FINISHED,
    "PEN": ProviderFixtureStatus.FINISHED,
    "PST": ProviderFixtureStatus.POSTPONED,
    "CANC": ProviderFixtureStatus.CANCELLED,
    "SUSP": ProviderFixtureStatus.SUSPENDED,
    "ABD": ProviderFixtureStatus.ABANDONED,
    "AWD": ProviderFixtureStatus.NOT_PLAYED,
    "WO": ProviderFixtureStatus.NOT_PLAYED,
}


@dataclass(frozen=True)
class ApiFootballFixtureParticipant:
    team_id: int
    role: str

    @property
    def external_id(self) -> str:
        return str(self.team_id)


@dataclass(frozen=True)
class ApiFootballFixture:
    id: int
    competition_id: int
    season_year: int
    participants: tuple[ApiFootballFixtureParticipant, ...]
    kickoff_utc: datetime | None
    kickoff_confirmed: bool
    status: ProviderFixtureStatus
    provider_status_code: str
    provider_status_reason: str
    stage: str | None
    round_name: str | None
    sequence_number: int | None
    venue_name: str | None
    venue_city: str | None
    source_updated_at: datetime | None

    @property
    def external_id(self) -> str:
        return str(self.id)


def parse_fixture(payload: dict[str, Any]) -> ApiFootballFixture:
    fixture = _required_object(payload, "fixture", "fixture response")
    league = _required_object(payload, "league", "fixture response")
    teams = _required_object(payload, "teams", "fixture response")
    home = _required_object(teams, "home", "fixture teams")
    away = _required_object(teams, "away", "fixture teams")
    status_payload = _required_object(fixture, "status", "fixture")

    home_id = _required_positive_integer(home, "id", "home team")
    away_id = _required_positive_integer(away, "id", "away team")
    if home_id == away_id:
        raise ProviderIntegrityError(
            "API-Football fixture home and away teams must be distinct."
        )

    status_code = _required_string(status_payload, "short", "fixture status")
    status = _map_status(status_code)
    kickoff_utc, kickoff_confirmed = _parse_kickoff(fixture, status_code)
    round_name = _optional_string(league, "round", "fixture league")
    stage, sequence_number = _parse_round(round_name)
    venue = fixture.get("venue")
    if venue is not None and not isinstance(venue, dict):
        raise ProviderResponseSchemaError(
            "API-Football fixture has invalid venue metadata."
        )

    return ApiFootballFixture(
        id=_required_positive_integer(fixture, "id", "fixture"),
        competition_id=_required_positive_integer(league, "id", "fixture league"),
        season_year=_required_positive_integer(league, "season", "fixture league"),
        participants=(
            ApiFootballFixtureParticipant(team_id=home_id, role="home"),
            ApiFootballFixtureParticipant(team_id=away_id, role="away"),
        ),
        kickoff_utc=kickoff_utc,
        kickoff_confirmed=kickoff_confirmed,
        status=status,
        provider_status_code=status_code,
        provider_status_reason=_required_string(
            status_payload,
            "long",
            "fixture status",
        ),
        stage=stage,
        round_name=round_name,
        sequence_number=sequence_number,
        venue_name=(
            _optional_string(venue, "name", "fixture venue")
            if venue is not None
            else None
        ),
        venue_city=(
            _optional_string(venue, "city", "fixture venue")
            if venue is not None
            else None
        ),
        source_updated_at=_optional_aware_datetime(
            fixture,
            "updated",
            "fixture",
        ),
    )


def _map_status(value: str) -> ProviderFixtureStatus:
    try:
        return STATUS_MAPPING[value]
    except KeyError as error:
        raise UnsupportedProviderValueError(
            f"API-Football fixture status is unsupported: {value}."
        ) from error


def _parse_kickoff(
    fixture: dict[str, Any],
    status_code: str,
) -> tuple[datetime | None, bool]:
    if status_code == "TBD":
        return None, False

    raw_timestamp = fixture.get("timestamp")
    raw_date = fixture.get("date")
    timestamp_value: datetime | None = None
    date_value: datetime | None = None

    if raw_timestamp is not None:
        if (
            not isinstance(raw_timestamp, int)
            or isinstance(raw_timestamp, bool)
            or raw_timestamp <= 0
        ):
            raise ProviderResponseSchemaError(
                "API-Football fixture has invalid timestamp metadata."
            )
        try:
            timestamp_value = datetime.fromtimestamp(raw_timestamp, UTC)
        except (OSError, OverflowError, ValueError) as error:
            raise ProviderResponseSchemaError(
                "API-Football fixture timestamp is outside the supported range."
            ) from error

    if raw_date is not None:
        if not isinstance(raw_date, str) or not raw_date.strip():
            raise ProviderResponseSchemaError(
                "API-Football fixture has invalid date metadata."
            )
        date_value = _parse_aware_datetime(raw_date, "fixture date")

    if timestamp_value is None and date_value is None:
        raise ProviderResponseSchemaError(
            "API-Football confirmed fixture kickoff is missing."
        )

    if (
        timestamp_value is not None
        and date_value is not None
        and timestamp_value != date_value
    ):
        raise ProviderIntegrityError(
            "API-Football fixture timestamp and date identify different instants."
        )

    kickoff = timestamp_value or date_value
    if kickoff is None:
        raise AssertionError("Validated fixture kickoff unexpectedly missing.")
    if not 2000 <= kickoff.year <= 2100:
        raise ProviderResponseSchemaError(
            "API-Football fixture kickoff is outside the supported range."
        )
    return kickoff.astimezone(UTC), True


def _parse_round(value: str | None) -> tuple[str | None, int | None]:
    if value is None:
        return None, None
    stage, separator, sequence = value.rpartition(" - ")
    if not separator:
        return value, None
    if not sequence.isdecimal() or int(sequence) <= 0:
        return value, None
    return stage.strip() or None, int(sequence)


def _optional_aware_datetime(
    payload: dict[str, Any],
    name: str,
    context: str,
) -> datetime | None:
    value = payload.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ProviderResponseSchemaError(
            f"API-Football {context} has invalid {name} metadata."
        )
    return _parse_aware_datetime(value, f"{context} {name}")


def _parse_aware_datetime(value: str, context: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ProviderResponseSchemaError(
            f"API-Football {context} is malformed."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ProviderResponseSchemaError(
            f"API-Football {context} must include an explicit timezone offset."
        )
    return parsed.astimezone(UTC)


def _required_object(
    payload: dict[str, Any],
    name: str,
    context: str,
) -> dict[str, Any]:
    value = payload.get(name)
    if not isinstance(value, dict):
        raise ProviderResponseSchemaError(
            f"API-Football {context} has invalid {name} metadata."
        )
    return value


def _required_positive_integer(
    payload: dict[str, Any],
    name: str,
    context: str,
) -> int:
    value = payload.get(name)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ProviderResponseSchemaError(
            f"API-Football {context} has invalid {name} metadata."
        )
    return value


def _required_string(
    payload: dict[str, Any],
    name: str,
    context: str,
) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ProviderResponseSchemaError(
            f"API-Football {context} has invalid {name} metadata."
        )
    return value.strip()


def _optional_string(
    payload: dict[str, Any],
    name: str,
    context: str,
) -> str | None:
    value = payload.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ProviderResponseSchemaError(
            f"API-Football {context} has invalid {name} metadata."
        )
    return value.strip()
