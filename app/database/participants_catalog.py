from dataclasses import dataclass

from app.database.competitions_repository import CompetitionsRepository
from app.database.participants_repository import Participant, ParticipantsRepository
from app.database.season_participants_repository import (
    SeasonParticipant,
    SeasonParticipantsRepository,
)
from app.database.seasons_repository import SeasonsRepository
from app.database.sports_repository import SportsRepository


@dataclass(frozen=True)
class ParticipantsCatalogResult:
    participants: list[Participant]
    season_participants: list[SeasonParticipant]


@dataclass(frozen=True)
class ParticipantCatalogEntry:
    participant_key: str
    name: str
    short_name: str


@dataclass(frozen=True)
class SeasonParticipantsCatalogEntry:
    competition_key: str
    season_key: str
    country_code: str
    participants: tuple[ParticipantCatalogEntry, ...]


PREMIER_LEAGUE_2026_27_TEAMS = (
    ("arsenal", "Arsenal", "Arsenal"),
    ("aston_villa", "Aston Villa", "Aston Villa"),
    ("bournemouth", "AFC Bournemouth", "Bournemouth"),
    ("brentford", "Brentford", "Brentford"),
    ("brighton_and_hove_albion", "Brighton & Hove Albion", "Brighton"),
    ("chelsea", "Chelsea", "Chelsea"),
    ("coventry_city", "Coventry City", "Coventry"),
    ("crystal_palace", "Crystal Palace", "Crystal Palace"),
    ("everton", "Everton", "Everton"),
    ("fulham", "Fulham", "Fulham"),
    ("hull_city", "Hull City", "Hull"),
    ("ipswich_town", "Ipswich Town", "Ipswich"),
    ("leeds_united", "Leeds United", "Leeds"),
    ("liverpool", "Liverpool", "Liverpool"),
    ("manchester_city", "Manchester City", "Man City"),
    ("manchester_united", "Manchester United", "Man Utd"),
    ("newcastle_united", "Newcastle United", "Newcastle"),
    ("nottingham_forest", "Nottingham Forest", "Nott'm Forest"),
    ("sunderland", "Sunderland", "Sunderland"),
    ("tottenham_hotspur", "Tottenham Hotspur", "Spurs"),
)

BUNDESLIGA_2026_27_TEAMS = (
    ("fc_koeln", "1. FC Köln", "1. FC Köln"),
    ("fc_union_berlin", "1. FC Union Berlin", "Union Berlin"),
    ("fsv_mainz_05", "1. FSV Mainz 05", "Mainz"),
    ("bayer_04_leverkusen", "Bayer 04 Leverkusen", "Leverkusen"),
    ("borussia_dortmund", "Borussia Dortmund", "Dortmund"),
    (
        "borussia_moenchengladbach",
        "Borussia Mönchengladbach",
        "M'gladbach",
    ),
    ("eintracht_frankfurt", "Eintracht Frankfurt", "Frankfurt"),
    ("fc_augsburg", "FC Augsburg", "Augsburg"),
    ("fc_bayern_muenchen", "FC Bayern München", "Bayern"),
    ("fc_schalke_04", "FC Schalke 04", "Schalke"),
    ("hamburger_sv", "Hamburger SV", "HSV"),
    ("rb_leipzig", "RB Leipzig", "RB Leipzig"),
    ("sc_freiburg", "SC Freiburg", "Freiburg"),
    ("sc_paderborn_07", "SC Paderborn 07", "SC Paderborn"),
    ("sv_elversberg", "SV 07 Elversberg", "Elversberg"),
    ("werder_bremen", "SV Werder Bremen", "Bremen"),
    ("tsg_hoffenheim", "TSG 1899 Hoffenheim", "Hoffenheim"),
    ("vfb_stuttgart", "VfB Stuttgart", "Stuttgart"),
)

SEASON_PARTICIPANTS_CATALOG = (
    SeasonParticipantsCatalogEntry(
        competition_key="premier_league",
        season_key="2026_27",
        country_code="GB-ENG",
        participants=tuple(
            ParticipantCatalogEntry(
                participant_key=participant_key,
                name=name,
                short_name=short_name,
            )
            for participant_key, name, short_name in PREMIER_LEAGUE_2026_27_TEAMS
        ),
    ),
    SeasonParticipantsCatalogEntry(
        competition_key="bundesliga",
        season_key="2026_27",
        country_code="DE",
        participants=tuple(
            ParticipantCatalogEntry(
                participant_key=participant_key,
                name=name,
                short_name=short_name,
            )
            for participant_key, name, short_name in BUNDESLIGA_2026_27_TEAMS
        ),
    ),
)


def initialize_participants_catalog(
    repository: ParticipantsRepository,
    season_participants_repository: SeasonParticipantsRepository,
    sports_repository: SportsRepository,
    competitions_repository: CompetitionsRepository,
    seasons_repository: SeasonsRepository,
) -> ParticipantsCatalogResult:
    football = sports_repository.get_by_key("football")
    if football is None:
        raise RuntimeError(
            "Required sport not found for participants catalog: football"
        )

    participants: list[Participant] = []
    memberships: list[SeasonParticipant] = []
    for catalog_entry in SEASON_PARTICIPANTS_CATALOG:
        competition = competitions_repository.get_by_key(
            sport_id=football.id,
            competition_key=catalog_entry.competition_key,
        )
        if competition is None:
            raise RuntimeError(
                "Required competition not found for participants catalog: "
                f"{catalog_entry.competition_key}"
            )
        season = seasons_repository.get_by_key(
            competition_id=competition.id,
            season_key=catalog_entry.season_key,
        )
        if season is None:
            raise RuntimeError(
                "Required season not found for participants catalog: "
                f"{catalog_entry.competition_key}/{catalog_entry.season_key}"
            )
        catalog_participants = [
            repository.upsert(
                sport_id=football.id,
                participant_key=entry.participant_key,
                participant_type="team",
                name=entry.name,
                short_name=entry.short_name,
                country_code=catalog_entry.country_code,
            )
            for entry in catalog_entry.participants
        ]
        participants.extend(catalog_participants)
        memberships.extend(
            season_participants_repository.upsert(
                season_id=season.id,
                participant_id=participant.id,
            )
            for participant in catalog_participants
        )

    return ParticipantsCatalogResult(
        participants=participants,
        season_participants=memberships,
    )
