from app.database.competitions_repository import (
    Competition,
    CompetitionsRepository,
)
from app.database.sports_repository import SportsRepository


def initialize_competitions_catalog(
    repository: CompetitionsRepository,
    sports_repository: SportsRepository,
) -> list[Competition]:
    football = sports_repository.get_by_key("football")

    if football is None:
        raise RuntimeError(
            "Required sport not found for competitions catalog: football"
        )

    return [
        repository.upsert(
            sport_id=football.id,
            competition_key="premier_league",
            name="Premier League",
            short_name="PL",
            country_code="GB-ENG",
            competition_type="league",
            metadata={
                "region": "England",
                "calendar_category": "SMART | England",
            },
        )
    ]
