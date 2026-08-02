from app.database.competitions_repository import CompetitionsRepository
from app.database.seasons_repository import Season, SeasonsRepository
from app.database.sports_repository import SportsRepository


def initialize_seasons_catalog(
    repository: SeasonsRepository,
    competitions_repository: CompetitionsRepository,
    sports_repository: SportsRepository,
) -> list[Season]:
    football = sports_repository.get_by_key("football")

    if football is None:
        raise RuntimeError("Required sport not found for seasons catalog: football")

    premier_league = competitions_repository.get_by_key(
        sport_id=football.id,
        competition_key="premier_league",
    )

    if premier_league is None:
        raise RuntimeError(
            "Required competition not found for seasons catalog: premier_league"
        )

    return [
        repository.upsert(
            competition_id=premier_league.id,
            season_key="2026_27",
            name="2026/27",
            start_date="2026-08-21",
            end_date="2027-05-30",
            is_current=True,
        )
    ]
