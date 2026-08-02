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

    premier_league = competitions_repository.get_by_key(
        sport_id=football.id,
        competition_key="premier_league",
    )
    if premier_league is None:
        raise RuntimeError(
            "Required competition not found for participants catalog: premier_league"
        )

    season = seasons_repository.get_by_key(
        competition_id=premier_league.id,
        season_key="2026_27",
    )
    if season is None:
        raise RuntimeError(
            "Required season not found for participants catalog: 2026_27"
        )

    participants = [
        repository.upsert(
            sport_id=football.id,
            participant_key=participant_key,
            participant_type="team",
            name=name,
            short_name=short_name,
            country_code="GB-ENG",
        )
        for participant_key, name, short_name in PREMIER_LEAGUE_2026_27_TEAMS
    ]
    memberships = [
        season_participants_repository.upsert(
            season_id=season.id,
            participant_id=participant.id,
        )
        for participant in participants
    ]

    return ParticipantsCatalogResult(
        participants=participants,
        season_participants=memberships,
    )
