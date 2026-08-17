from dataclasses import dataclass


@dataclass(frozen=True)
class FootballDataCompetitionMapping:
    competition_key: str
    external_code: str
    external_id: int

    def __post_init__(self) -> None:
        if not self.competition_key or not self.external_code:
            raise ValueError("Football-data.org competition identity is required.")
        if self.external_id <= 0:
            raise ValueError("Football-data.org competition ID must be positive.")


PREMIER_LEAGUE_MAPPING = FootballDataCompetitionMapping(
    competition_key="premier_league",
    external_code="PL",
    external_id=2021,
)
BUNDESLIGA_MAPPING = FootballDataCompetitionMapping(
    competition_key="bundesliga",
    external_code="BL1",
    external_id=2002,
)

FOOTBALL_DATA_COMPETITION_MAPPINGS = {
    mapping.competition_key: mapping
    for mapping in (PREMIER_LEAGUE_MAPPING, BUNDESLIGA_MAPPING)
}


def get_competition_mapping(
    competition_key: str,
) -> FootballDataCompetitionMapping | None:
    return FOOTBALL_DATA_COMPETITION_MAPPINGS.get(competition_key)
