from copy import deepcopy

import pytest
from app.providers.api_football.catalog_models import parse_league, parse_team
from app.providers.api_football.exceptions import ProviderResponseSchemaError

from tests.providers.api_football.catalog_test_support import load_envelope


def test_parse_league_returns_typed_competition_and_seasons() -> None:
    payload = load_envelope("premier_league.json")["response"][0]

    league = parse_league(payload)

    assert league.id == 39
    assert league.external_id == "39"
    assert league.name == "Premier League"
    assert league.league_type == "League"
    assert league.country_name == "England"
    assert league.country_code == "GB"
    assert len(league.seasons) == 2
    assert league.seasons[1].year == 2026
    assert league.seasons[1].external_id == "2026"
    assert league.seasons[1].is_current is True


@pytest.mark.parametrize(
    "mutate",
    [
        lambda item: item["league"].__setitem__("id", None),
        lambda item: item["league"].__setitem__("id", 0),
        lambda item: item["league"].__setitem__("name", ""),
        lambda item: item.__setitem__("seasons", None),
        lambda item: item["seasons"][1].__setitem__("year", "2026"),
        lambda item: item["seasons"][1].__setitem__("start", "invalid"),
        lambda item: item["seasons"][1].__setitem__("current", "true"),
    ],
)
def test_parse_league_rejects_malformed_stable_data(mutate: object) -> None:
    payload = deepcopy(load_envelope("premier_league.json")["response"][0])
    mutate(payload)  # type: ignore[operator]

    with pytest.raises(ProviderResponseSchemaError):
        parse_league(payload)


def test_parse_team_returns_typed_safe_metadata() -> None:
    payload = load_envelope("premier_league_teams.json")["response"][0]

    team = parse_team(payload)

    assert team.id == 42
    assert team.external_id == "42"
    assert team.name == "Arsenal"
    assert team.code == "ARS"
    assert team.country == "England"
    assert team.logo_url == "https://media.api-sports.io/football/teams/42.png"
    assert team.venue_name == "Emirates Stadium"
    assert team.venue_city == "London"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda item: item["team"].__setitem__("id", None),
        lambda item: item["team"].__setitem__("id", -1),
        lambda item: item["team"].__setitem__("name", " "),
        lambda item: item["team"].__setitem__("national", "false"),
        lambda item: item["team"].__setitem__("national", True),
        lambda item: item["team"].__setitem__(
            "logo", "https://user:secret@provider.example/logo.png"
        ),
        lambda item: item.__setitem__("venue", []),
    ],
)
def test_parse_team_rejects_malformed_stable_data(mutate: object) -> None:
    payload = deepcopy(load_envelope("premier_league_teams.json")["response"][0])
    mutate(payload)  # type: ignore[operator]

    with pytest.raises(ProviderResponseSchemaError):
        parse_team(payload)
