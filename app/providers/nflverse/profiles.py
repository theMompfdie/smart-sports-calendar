from dataclasses import dataclass
from datetime import date

from app.domain.competition_lifecycle import FixtureObservationScopeKind


@dataclass(frozen=True)
class NflverseCompetitionProfile:
    sport_key: str
    competition_key: str
    season_key: str
    season: int
    game_type: str
    expected_game_count: int
    expected_team_count: int
    expected_weeks: frozenset[int]
    season_start_date: date
    season_end_date: date
    lifecycle_scope_kind: FixtureObservationScopeKind = (
        FixtureObservationScopeKind.PARTIAL
    )


NFL_2026_REGULAR_SEASON_PROFILE = NflverseCompetitionProfile(
    sport_key="american_football",
    competition_key="nfl",
    season_key="2026",
    season=2026,
    game_type="REG",
    expected_game_count=272,
    expected_team_count=32,
    expected_weeks=frozenset(range(1, 19)),
    season_start_date=date(2026, 9, 9),
    season_end_date=date(2027, 1, 10),
)
