from dataclasses import dataclass

from app.database.competitions_repository import CompetitionsRepository
from app.database.seasons_repository import Season, SeasonsRepository
from app.database.sports_repository import SportsRepository


@dataclass(frozen=True)
class SeasonCatalogEntry:
    sport_key: str
    competition_key: str
    season_key: str
    name: str
    start_date: str
    end_date: str
    is_current: bool = True


SEASON_CATALOG = (
    SeasonCatalogEntry(
        sport_key="football",
        competition_key="premier_league",
        season_key="2026_27",
        name="2026/27",
        start_date="2026-08-21",
        end_date="2027-05-30",
    ),
    SeasonCatalogEntry(
        sport_key="football",
        competition_key="bundesliga",
        season_key="2026_27",
        name="2026/27",
        start_date="2026-08-28",
        end_date="2027-05-22",
    ),
    SeasonCatalogEntry(
        sport_key="football",
        competition_key="austrian_bundesliga",
        season_key="2026_27",
        name="2026/27",
        start_date="2026-07-31",
        end_date="2027-05-31",
    ),
    SeasonCatalogEntry(
        sport_key="football",
        competition_key="championship",
        season_key="2026_27",
        name="2026/27",
        start_date="2026-08-14",
        end_date="2027-05-01",
    ),
    SeasonCatalogEntry(
        sport_key="football",
        competition_key="efl_cup",
        season_key="2026_27",
        name="2026/27",
        start_date="2026-08-01",
        end_date="2027-03-21",
    ),
    SeasonCatalogEntry(
        sport_key="football",
        competition_key="fa_cup",
        season_key="2026_27",
        name="2026/27",
        start_date="2026-08-08",
        end_date="2027-05-22",
    ),
    SeasonCatalogEntry(
        sport_key="football",
        competition_key="second_bundesliga",
        season_key="2026_27",
        name="2026/27",
        start_date="2026-08-07",
        end_date="2027-05-23",
    ),
    SeasonCatalogEntry(
        sport_key="football",
        competition_key="dfb_pokal",
        season_key="2026_27",
        name="2026/27",
        start_date="2026-08-21",
        end_date="2027-05-29",
    ),
    SeasonCatalogEntry(
        sport_key="football",
        competition_key="oefb_cup",
        season_key="2026_27",
        name="2026/27",
        start_date="2026-07-01",
        end_date="2027-06-30",
    ),
    SeasonCatalogEntry(
        sport_key="football",
        competition_key="uefa_nations_league",
        season_key="2026_27",
        name="2026/27 league phase",
        start_date="2026-09-24",
        end_date="2026-11-17",
    ),
    SeasonCatalogEntry(
        sport_key="football",
        competition_key="uefa_conference_league",
        season_key="2026_27",
        name="2026/27 league phase",
        start_date="2026-10-15",
        end_date="2026-12-17",
    ),
    SeasonCatalogEntry(
        sport_key="football",
        competition_key="uefa_champions_league",
        season_key="2026_27",
        name="2026/27 league phase",
        start_date="2026-09-08",
        end_date="2027-01-27",
    ),
    SeasonCatalogEntry(
        sport_key="american_football",
        competition_key="nfl",
        season_key="2026",
        name="2026 regular season",
        start_date="2026-09-09",
        end_date="2027-01-10",
    ),
)


def initialize_seasons_catalog(
    repository: SeasonsRepository,
    competitions_repository: CompetitionsRepository,
    sports_repository: SportsRepository,
) -> list[Season]:
    seasons: list[Season] = []
    for entry in SEASON_CATALOG:
        sport = sports_repository.get_by_key(entry.sport_key)
        if sport is None:
            raise RuntimeError(
                f"Required sport not found for seasons catalog: {entry.sport_key}"
            )
        competition = competitions_repository.get_by_key(
            sport_id=sport.id,
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
