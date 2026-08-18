from dataclasses import dataclass

from app.providers.football_data.competition_mappings import (
    BUNDESLIGA_MAPPING,
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

FOOTBALL_DATA_COMPETITION_PROFILES = {
    (profile.competition_key, profile.season_key): profile
    for profile in (PREMIER_LEAGUE_PROFILE, BUNDESLIGA_PROFILE)
}


def get_competition_profile(
    competition_key: str,
    season_key: str,
) -> FootballDataCompetitionProfile | None:
    return FOOTBALL_DATA_COMPETITION_PROFILES.get((competition_key, season_key))
