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
)
