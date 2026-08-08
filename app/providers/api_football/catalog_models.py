from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import urlsplit

from app.providers.api_football.exceptions import ProviderResponseSchemaError


@dataclass(frozen=True)
class ApiFootballSeason:
    year: int
    start_date: date
    end_date: date
    is_current: bool

    @property
    def external_id(self) -> str:
        return str(self.year)


@dataclass(frozen=True)
class ApiFootballLeague:
    id: int
    name: str
    league_type: str
    country_name: str
    country_code: str | None
    seasons: tuple[ApiFootballSeason, ...]

    @property
    def external_id(self) -> str:
        return str(self.id)


@dataclass(frozen=True)
class ApiFootballTeam:
    id: int
    name: str
    code: str | None
    country: str | None
    logo_url: str | None
    venue_name: str | None
    venue_city: str | None

    @property
    def external_id(self) -> str:
        return str(self.id)


def parse_league(payload: dict[str, Any]) -> ApiFootballLeague:
    league = _required_object(payload, "league", "league response")
    country = _required_object(payload, "country", "league response")
    raw_seasons = payload.get("seasons")

    if not isinstance(raw_seasons, list):
        raise ProviderResponseSchemaError(
            "API-Football league response has invalid seasons metadata."
        )

    seasons = tuple(
        parse_season(_object_item(item, "league seasons")) for item in raw_seasons
    )

    return ApiFootballLeague(
        id=_required_positive_integer(league, "id", "league"),
        name=_required_string(league, "name", "league"),
        league_type=_required_string(league, "type", "league"),
        country_name=_required_string(country, "name", "league country"),
        country_code=_optional_string(country, "code", "league country"),
        seasons=seasons,
    )


def parse_season(payload: dict[str, Any]) -> ApiFootballSeason:
    year = _required_positive_integer(payload, "year", "season")
    start_date = _required_date(payload, "start", "season")
    end_date = _required_date(payload, "end", "season")
    is_current = payload.get("current")

    if not isinstance(is_current, bool):
        raise ProviderResponseSchemaError(
            "API-Football season has invalid current metadata."
        )
    if end_date < start_date:
        raise ProviderResponseSchemaError(
            "API-Football season end date precedes its start date."
        )

    return ApiFootballSeason(
        year=year,
        start_date=start_date,
        end_date=end_date,
        is_current=is_current,
    )


def parse_team(payload: dict[str, Any]) -> ApiFootballTeam:
    team = _required_object(payload, "team", "team response")
    venue = payload.get("venue")

    if venue is not None and not isinstance(venue, dict):
        raise ProviderResponseSchemaError(
            "API-Football team response has invalid venue metadata."
        )

    national = team.get("national")
    if not isinstance(national, bool):
        raise ProviderResponseSchemaError(
            "API-Football team has invalid national metadata."
        )
    if national:
        raise ProviderResponseSchemaError(
            "API-Football Premier League response contains a national team."
        )

    logo_url = _optional_string(team, "logo", "team")
    if logo_url is not None:
        _validate_safe_https_url(logo_url, "team logo")

    return ApiFootballTeam(
        id=_required_positive_integer(team, "id", "team"),
        name=_required_string(team, "name", "team"),
        code=_optional_string(team, "code", "team"),
        country=_optional_string(team, "country", "team"),
        logo_url=logo_url,
        venue_name=(
            _optional_string(venue, "name", "team venue") if venue is not None else None
        ),
        venue_city=(
            _optional_string(venue, "city", "team venue") if venue is not None else None
        ),
    )


def _object_item(value: object, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProviderResponseSchemaError(
            f"API-Football {context} must contain objects."
        )
    return value


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


def _required_date(
    payload: dict[str, Any],
    name: str,
    context: str,
) -> date:
    value = _required_string(payload, name, context)
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ProviderResponseSchemaError(
            f"API-Football {context} has invalid {name} date metadata."
        ) from error


def _validate_safe_https_url(value: str, context: str) -> None:
    parsed_url = urlsplit(value)
    if (
        parsed_url.scheme != "https"
        or not parsed_url.hostname
        or parsed_url.username is not None
        or parsed_url.password is not None
        or parsed_url.query
        or parsed_url.fragment
    ):
        raise ProviderResponseSchemaError(
            f"API-Football {context} must be a safe HTTPS URL."
        )
