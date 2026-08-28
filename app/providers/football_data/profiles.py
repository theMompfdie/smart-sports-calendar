from dataclasses import dataclass

from app.domain.competition_lifecycle import FixtureObservationScopeKind
from app.providers.football_data.competition_mappings import (
    BUNDESLIGA_MAPPING,
    CHAMPIONSHIP_MAPPING,
    PREMIER_LEAGUE_MAPPING,
)


@dataclass(frozen=True)
class FootballDataCompetitionProfile:
    competition_key: str
    competition_name: str
    season_key: str
    external_code: str
    external_id: int
    external_season_id: int
    expected_team_count: int
    expected_match_count: int
    expected_matchdays: int
    lifecycle_scope_kind: FixtureObservationScopeKind = (
        FixtureObservationScopeKind.COMPLETE_SEASON
    )
    match_stage_filter: str | None = None

    def __post_init__(self) -> None:
        if not self.competition_key or not self.competition_name or not self.season_key:
            raise ValueError("Football-data.org profile identity is required.")
        if not self.external_code:
            raise ValueError("Football-data.org provider code is required.")
        if self.external_id <= 0 or self.external_season_id <= 0:
            raise ValueError("Football-data.org provider IDs must be positive.")
        if self.expected_team_count <= 0 or self.expected_team_count % 2:
            raise ValueError("Football-data.org profile requires an even team count.")
        if self.expected_matchdays != (self.expected_team_count - 1) * 2:
            raise ValueError(
                "Football-data.org profile has invalid matchday semantics."
            )
        if self.expected_match_count != (
            self.expected_team_count * (self.expected_team_count - 1)
        ):
            raise ValueError(
                "Football-data.org profile is not a complete double round robin."
            )
        if self.lifecycle_scope_kind is FixtureObservationScopeKind.COMPLETE_SEASON:
            if self.match_stage_filter is not None:
                raise ValueError(
                    "A complete-season football-data.org profile cannot declare "
                    "a stage filter."
                )
        elif self.lifecycle_scope_kind is FixtureObservationScopeKind.COMPLETE_STAGE:
            if (
                self.match_stage_filter is None
                or not self.match_stage_filter.strip()
                or self.match_stage_filter != self.match_stage_filter.strip()
            ):
                raise ValueError(
                    "A complete-stage football-data.org profile requires a "
                    "normalized stage filter."
                )
        else:
            raise ValueError(
                "Football-data.org profile has an unsupported lifecycle scope."
            )


PREMIER_LEAGUE_PROFILE = FootballDataCompetitionProfile(
    competition_key="premier_league",
    competition_name="Premier League",
    season_key="2026_27",
    external_code=PREMIER_LEAGUE_MAPPING.external_code,
    external_id=PREMIER_LEAGUE_MAPPING.external_id,
    external_season_id=2502,
    expected_team_count=20,
    expected_match_count=380,
    expected_matchdays=38,
)
BUNDESLIGA_PROFILE = FootballDataCompetitionProfile(
    competition_key="bundesliga",
    competition_name="Bundesliga",
    season_key="2026_27",
    external_code=BUNDESLIGA_MAPPING.external_code,
    external_id=BUNDESLIGA_MAPPING.external_id,
    external_season_id=2522,
    expected_team_count=18,
    expected_match_count=306,
    expected_matchdays=34,
)
CHAMPIONSHIP_PROFILE = FootballDataCompetitionProfile(
    competition_key="championship",
    competition_name="EFL Championship",
    season_key="2026_27",
    external_code=CHAMPIONSHIP_MAPPING.external_code,
    external_id=CHAMPIONSHIP_MAPPING.external_id,
    external_season_id=2509,
    expected_team_count=24,
    expected_match_count=552,
    expected_matchdays=46,
    lifecycle_scope_kind=FixtureObservationScopeKind.COMPLETE_STAGE,
    match_stage_filter="REGULAR_SEASON",
)

FOOTBALL_DATA_COMPETITION_PROFILES = {
    (profile.competition_key, profile.season_key): profile
    for profile in (
        PREMIER_LEAGUE_PROFILE,
        BUNDESLIGA_PROFILE,
        CHAMPIONSHIP_PROFILE,
    )
}


def get_competition_profile(
    competition_key: str,
    season_key: str,
) -> FootballDataCompetitionProfile | None:
    return FOOTBALL_DATA_COMPETITION_PROFILES.get((competition_key, season_key))
