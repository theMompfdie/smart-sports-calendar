import pytest
from app.providers.football_data.competition_mappings import (
    BUNDESLIGA_MAPPING,
    PREMIER_LEAGUE_MAPPING,
    FootballDataCompetitionMapping,
    get_competition_mapping,
)
from app.providers.football_data.team_mappings import resolve_team_key


def test_reviewed_competition_mappings_keep_provider_identity_scoped() -> None:
    assert get_competition_mapping("premier_league") == PREMIER_LEAGUE_MAPPING
    assert PREMIER_LEAGUE_MAPPING.external_code == "PL"
    assert PREMIER_LEAGUE_MAPPING.external_id == 2021

    assert get_competition_mapping("bundesliga") == BUNDESLIGA_MAPPING
    assert BUNDESLIGA_MAPPING.external_code == "BL1"
    assert BUNDESLIGA_MAPPING.external_id == 2002
    assert get_competition_mapping("unknown") is None


def test_competition_mapping_rejects_invalid_identity() -> None:
    with pytest.raises(ValueError, match="identity is required"):
        FootballDataCompetitionMapping("", "BL1", 2002)
    with pytest.raises(ValueError, match="ID must be positive"):
        FootballDataCompetitionMapping("bundesliga", "BL1", 0)


def test_team_resolution_is_competition_scoped() -> None:
    assert resolve_team_key("premier_league", "Arsenal FC") == "arsenal"
    assert resolve_team_key("bundesliga", "Arsenal FC") is None
    assert resolve_team_key("unknown", "Arsenal FC") is None
