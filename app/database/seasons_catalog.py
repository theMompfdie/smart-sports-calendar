from dataclasses import dataclass

from app.database.competitions_repository import CompetitionsRepository
from app.database.seasons_repository import Season, SeasonsRepository
from app.database.sports_repository import SportsRepository


@dataclass(frozen=True)
class SeasonCatalogEntry:
    competition_key: str
    season_key: str
    name: str
    start_date: str
    end_date: str
    is_current: bool = True


SEASON_CATALOG = (
    SeasonCatalogEntry(
        competition_key="premier_league",
        season_key="2026_27",
        name="2026/27",
        start_date="2026-08-21",
        end_date="2027-05-30",
    ),
    SeasonCatalogEntry(
        competition_key="bundesliga",
        season_key="2026_27",
        name="2026/27",
        start_date="2026-08-28",
        end_date="2027-05-22",
    ),
    SeasonCatalogEntry(
        competition_key="dfb_pokal",
        season_key="2026_27",
        name="2026/27",
        start_date="2026-08-21",
        end_date="2027-05-29",
    ),
)


def initialize_seasons_catalog(
    repository: SeasonsRepository,
    competitions_repository: CompetitionsRepository,
    sports_repository: SportsRepository,
) -> list[Season]:
    football = sports_repository.get_by_key("football")

    if football is None:
        raise RuntimeError("Required sport not found for seasons catalog: football")

    seasons: list[Season] = []
    for entry in SEASON_CATALOG:
        competition = competitions_repository.get_by_key(
            sport_id=football.id,
            competition_key=entry.competition_key,
        )
        if competition is None:
            raise RuntimeError(
                "Required competition not found for seasons catalog: "
                f"{entry.competition_key}"
            )
        seasons.append(
            repository.upsert(
                competition_id=competition.id,
                season_key=entry.season_key,
                name=entry.name,
                start_date=entry.start_date,
                end_date=entry.end_date,
                is_current=entry.is_current,
            )
        )
    return seasons
