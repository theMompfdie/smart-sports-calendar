from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class OpenLigaDBCompetitionProfile:
    canonical_competition_key: str
    canonical_season_key: str
    competition_name: str
    league_id: int
    league_shortcut: str
    league_season: int
    sport_id: int
    season_start_date: date
    season_end_date: date
    round_capacities: tuple[int, ...]
    normalized_stage: str
    round_prefix: str
    expected_fixture_count: int | None = None
    expected_participant_count: int | None = None
    require_complete_double_round_robin: bool = False
    allow_missing_timezone_id: bool = False


DFB_POKAL_PROFILE = OpenLigaDBCompetitionProfile(
    canonical_competition_key="dfb_pokal",
    canonical_season_key="2026_27",
    competition_name="DFB-Pokal",
    league_id=4945,
    league_shortcut="dfb",
    league_season=2026,
    sport_id=1,
    season_start_date=date(2026, 8, 21),
    season_end_date=date(2027, 5, 29),
    round_capacities=(32, 16, 8, 4, 2, 1),
    normalized_stage="knockout",
    round_prefix="round",
    allow_missing_timezone_id=True,
)

SECOND_BUNDESLIGA_PROFILE = OpenLigaDBCompetitionProfile(
    canonical_competition_key="second_bundesliga",
    canonical_season_key="2026_27",
    competition_name="2. Bundesliga",
    league_id=4938,
    league_shortcut="bl2",
    league_season=2026,
    sport_id=1,
    season_start_date=date(2026, 8, 7),
    season_end_date=date(2027, 5, 23),
    round_capacities=(9,) * 34,
    normalized_stage="regular_season",
    round_prefix="matchday",
    expected_fixture_count=306,
    expected_participant_count=18,
    require_complete_double_round_robin=True,
    allow_missing_timezone_id=True,
)

OPENLIGADB_COMPETITION_PROFILES = {
    (profile.canonical_competition_key, profile.canonical_season_key): profile
    for profile in (DFB_POKAL_PROFILE, SECOND_BUNDESLIGA_PROFILE)
}


def get_competition_profile(
    competition_key: str, season_key: str
) -> OpenLigaDBCompetitionProfile | None:
    return OPENLIGADB_COMPETITION_PROFILES.get((competition_key, season_key))
