import sqlite3
from pathlib import Path

import pytest
from app.database.competitions_catalog import initialize_competitions_catalog
from app.database.competitions_repository import CompetitionsRepository
from app.database.database import Database
from app.database.participants_catalog import initialize_participants_catalog
from app.database.participants_repository import ParticipantsRepository
from app.database.season_participants_repository import SeasonParticipantsRepository
from app.database.seasons_catalog import initialize_seasons_catalog
from app.database.seasons_repository import SeasonsRepository
from app.database.sports_catalog import initialize_sports_catalog
from app.database.sports_repository import SportsRepository


def create_repositories(tmp_path: Path):
    database_path = tmp_path / "sports.db"
    Database(database_path).initialize()
    sports = SportsRepository(database_path)
    competitions = CompetitionsRepository(database_path)
    seasons = SeasonsRepository(database_path)
    participants = ParticipantsRepository(database_path)
    memberships = SeasonParticipantsRepository(database_path)
    initialize_sports_catalog(sports)
    initialize_competitions_catalog(competitions, sports)
    initialize_seasons_catalog(seasons, competitions, sports)
    return database_path, sports, competitions, seasons, participants, memberships


def initialize(tmp_path: Path):
    repositories = create_repositories(tmp_path)
    _, sports, competitions, seasons, participants, memberships = repositories
    result = initialize_participants_catalog(
        participants, memberships, sports, competitions, seasons
    )
    return repositories, result


def test_catalog_creates_and_assigns_reviewed_competition_teams(
    tmp_path: Path,
) -> None:
    repositories, result = initialize(tmp_path)
    database_path = repositories[0]
    assert len(result.participants) == 506
    assert len(result.season_participants) == 506
    assert {item.participant_key for item in result.participants} >= {
        "arsenal",
        "coventry_city",
        "fc_bayern_muenchen",
        "fc_koeln",
        "hull_city",
        "ipswich_town",
        "sv_elversberg",
        "sc_st_toenis",
        "hamburg_eimsbuetteler_bc",
        "fc_heidenheim",
        "birmingham_city",
        "cardiff_city",
        "wrexham",
        "newport_county",
        "york_city",
        "fk_austria_wien",
        "sk_rapid",
        "wolfsberger_ac",
        "france",
        "germany",
        "england_national_team",
        "wales_national_team",
        "aek_athens",
        "paris_saint_germain",
        "sabah",
        "austria",
        "liechtenstein",
        "mjallby",
        "lincoln_red_imps",
        "arizona_cardinals",
        "kansas_city_chiefs",
        "washington_commanders",
    }
    assert all(item.participant_type == "team" for item in result.participants)
    with sqlite3.connect(database_path) as connection:
        membership_counts = connection.execute(
            """
            SELECT competition.competition_key, COUNT(*)
            FROM season_participants AS membership
            JOIN seasons AS season ON season.id = membership.season_id
            JOIN competitions AS competition ON competition.id = season.competition_id
            GROUP BY competition.competition_key
            ORDER BY competition.competition_key
            """
        ).fetchall()
    assert membership_counts == [
        ("austrian_bundesliga", 12),
        ("bundesliga", 18),
        ("championship", 24),
        ("dfb_pokal", 64),
        ("efl_cup", 92),
        ("nfl", 32),
        ("oefb_cup", 64),
        ("premier_league", 20),
        ("second_bundesliga", 18),
        ("uefa_champions_league", 36),
        ("uefa_conference_league", 36),
        ("uefa_europa_league", 36),
        ("uefa_nations_league", 54),
    ]
    countries_by_key = {
        participant.participant_key: participant.country_code
        for participant in result.participants
    }
    assert countries_by_key["arsenal"] == "GB-ENG"
    assert countries_by_key["fc_bayern_muenchen"] == "DE"
    assert countries_by_key["cardiff_city"] == "GB-WLS"
    assert countries_by_key["swansea_city"] == "GB-WLS"
    assert countries_by_key["wrexham"] == "GB-WLS"
    assert countries_by_key["newport_county"] == "GB-WLS"
    assert countries_by_key["birmingham_city"] == "GB-ENG"
    assert countries_by_key["fk_austria_wien"] == "AT"
    assert countries_by_key["france"] == "FR"
    assert countries_by_key["england_national_team"] == "GB-ENG"
    assert countries_by_key["aek_athens"] == "GR"
    assert countries_by_key["sabah"] == "AZ"
    assert countries_by_key["austria"] == "AT"
    assert countries_by_key["scotland"] == "GB-SCT"
    assert countries_by_key["kosovo"] == "XK"
    assert countries_by_key["mjallby"] == "SE"
    assert countries_by_key["lincoln_red_imps"] == "GI"


def test_catalog_assigns_relegated_teams_to_championship(tmp_path: Path) -> None:
    _, result = initialize(tmp_path)
    keys = {item.participant_key for item in result.participants}
    assert keys >= {"burnley", "west_ham_united", "wolverhampton_wanderers"}


def test_catalog_can_run_repeatedly(tmp_path: Path) -> None:
    repositories, first = initialize(tmp_path)
    (
        database_path,
        sports,
        competitions,
        seasons,
        participants,
        memberships,
    ) = repositories
    second = initialize_participants_catalog(
        participants, memberships, sports, competitions, seasons
    )
    with sqlite3.connect(database_path) as connection:
        participant_count = connection.execute(
            "SELECT COUNT(*) FROM participants"
        ).fetchone()
        membership_count = connection.execute(
            "SELECT COUNT(*) FROM season_participants"
        ).fetchone()
    assert participant_count == (395,)
    assert membership_count == (506,)
    assert [item.id for item in second.participants] == [
        item.id for item in first.participants
    ]


def test_catalog_restores_participant_master_data(tmp_path: Path) -> None:
    repositories = create_repositories(tmp_path)
    _, sports, competitions, seasons, participants, memberships = repositories
    football = sports.get_by_key("football")
    assert football is not None
    participants.upsert(football.id, "arsenal", "individual", "Wrong")
    initialize_participants_catalog(
        participants, memberships, sports, competitions, seasons
    )
    arsenal = participants.get_by_key(football.id, "arsenal")
    assert arsenal is not None
    assert arsenal.name == "Arsenal"
    assert arsenal.participant_type == "team"
    assert arsenal.country_code == "GB-ENG"

    participants.upsert(football.id, "fc_koeln", "individual", "Wrong")
    initialize_participants_catalog(
        participants, memberships, sports, competitions, seasons
    )
    fc_koeln = participants.get_by_key(football.id, "fc_koeln")
    assert fc_koeln is not None
    assert fc_koeln.name == "1. FC Köln"
    assert fc_koeln.short_name == "1. FC Köln"
    assert fc_koeln.participant_type == "team"
    assert fc_koeln.country_code == "DE"


def test_catalog_requires_current_season(tmp_path: Path) -> None:
    database_path = tmp_path / "sports.db"
    Database(database_path).initialize()
    sports = SportsRepository(database_path)
    competitions = CompetitionsRepository(database_path)
    initialize_sports_catalog(sports)
    initialize_competitions_catalog(competitions, sports)
    with pytest.raises(RuntimeError, match="Required season not found.*2026_27"):
        initialize_participants_catalog(
            ParticipantsRepository(database_path),
            SeasonParticipantsRepository(database_path),
            sports,
            competitions,
            SeasonsRepository(database_path),
        )
