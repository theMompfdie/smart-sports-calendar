import pytest
from app.providers.football_data.profiles import (
    BUNDESLIGA_PROFILE,
    PREMIER_LEAGUE_PROFILE,
    FootballDataCompetitionProfile,
    get_competition_profile,
)


def test_reviewed_profiles_resolve_by_canonical_scope() -> None:
    assert (
        get_competition_profile("premier_league", "2026_27") == PREMIER_LEAGUE_PROFILE
    )
    assert get_competition_profile("bundesliga", "2026_27") == BUNDESLIGA_PROFILE
    assert get_competition_profile("bundesliga", "2025_26") is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"competition_key": ""},
        {"external_id": 0},
        {"external_season_id": 0},
        {"expected_team_count": 17},
        {"expected_matchdays": 32},
        {"expected_match_count": 304},
    ],
)
def test_profile_rejects_invalid_reviewed_scope(overrides: dict[str, object]) -> None:
    values: dict[str, object] = {
        "competition_key": "bundesliga",
        "competition_name": "Bundesliga",
        "season_key": "2026_27",
        "external_code": "BL1",
        "external_id": 2002,
        "external_season_id": 2522,
        "expected_team_count": 18,
        "expected_match_count": 306,
        "expected_matchdays": 34,
    }
    values.update(overrides)

    with pytest.raises(ValueError):
        FootballDataCompetitionProfile(**values)  # type: ignore[arg-type]
