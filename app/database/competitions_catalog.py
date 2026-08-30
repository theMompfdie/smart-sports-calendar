from dataclasses import dataclass

from app.database.competitions_repository import (
    Competition,
    CompetitionsRepository,
)
from app.database.sports_repository import SportsRepository
from app.domain.competition_lifecycle import CompetitionFormat


@dataclass(frozen=True)
class CompetitionCatalogEntry:
    sport_key: str
    competition_key: str
    name: str
    short_name: str
    country_code: str
    competition_format: CompetitionFormat
    region: str
    calendar_category: str


COMPETITION_CATALOG = (
    CompetitionCatalogEntry(
        sport_key="football",
        competition_key="premier_league",
        name="Premier League",
        short_name="PL",
        country_code="GB-ENG",
        competition_format=CompetitionFormat.LEAGUE,
        region="England",
        calendar_category="SMART | England",
    ),
    CompetitionCatalogEntry(
        sport_key="football",
        competition_key="bundesliga",
        name="Bundesliga",
        short_name="BL",
        country_code="DE",
        competition_format=CompetitionFormat.LEAGUE,
        region="Germany",
        calendar_category="SMART | Germany",
    ),
    CompetitionCatalogEntry(
        sport_key="football",
        competition_key="championship",
        name="EFL Championship",
        short_name="EFL",
        country_code="GB-ENG",
        competition_format=CompetitionFormat.LEAGUE,
        region="England",
        calendar_category="SMART | England",
    ),
    CompetitionCatalogEntry(
        sport_key="football",
        competition_key="second_bundesliga",
        name="2. Bundesliga",
        short_name="2BL",
        country_code="DE",
        competition_format=CompetitionFormat.LEAGUE,
        region="Germany",
        calendar_category="SMART | Germany",
    ),
    CompetitionCatalogEntry(
        sport_key="football",
        competition_key="dfb_pokal",
        name="DFB-Pokal",
        short_name="DFB",
        country_code="DE",
        competition_format=CompetitionFormat.KNOCKOUT_CUP,
        region="Germany",
        calendar_category="SMART | Germany",
    ),
    CompetitionCatalogEntry(
        sport_key="football",
        competition_key="oefb_cup",
        name="UNIQA ÖFB Cup",
        short_name="ÖFB Cup",
        country_code="AT",
        competition_format=CompetitionFormat.KNOCKOUT_CUP,
        region="Austria",
        calendar_category="SMART | Austria",
    ),
    CompetitionCatalogEntry(
        sport_key="football",
        competition_key="uefa_nations_league",
        name="UEFA Nations League",
        short_name="UNL",
        country_code="INT",
        competition_format=CompetitionFormat.HYBRID_TOURNAMENT,
        region="Europe",
        calendar_category="SMART | UEFA",
    ),
    CompetitionCatalogEntry(
        sport_key="american_football",
        competition_key="nfl",
        name="National Football League",
        short_name="NFL",
        country_code="US",
        competition_format=CompetitionFormat.LEAGUE,
        region="United States",
        calendar_category="SMART | NFL",
    ),
)


def initialize_competitions_catalog(
    repository: CompetitionsRepository,
    sports_repository: SportsRepository,
) -> list[Competition]:
    competitions: list[Competition] = []
    for entry in COMPETITION_CATALOG:
        sport = sports_repository.get_by_key(entry.sport_key)
        if sport is None:
            raise RuntimeError(
                f"Required sport not found for competitions catalog: {entry.sport_key}"
            )
        competitions.append(
            repository.upsert(
                sport_id=sport.id,
                competition_key=entry.competition_key,
                name=entry.name,
                short_name=entry.short_name,
                country_code=entry.country_code,
                competition_type=entry.competition_format,
                metadata={
                    "region": entry.region,
                    "calendar_category": entry.calendar_category,
                },
            )
        )
    return competitions
