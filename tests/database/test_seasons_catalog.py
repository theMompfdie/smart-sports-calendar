import sqlite3
from pathlib import Path

import pytest
from app.database.competitions_catalog import (
    initialize_competitions_catalog,
)
from app.database.competitions_repository import CompetitionsRepository
from app.database.database import Database
from app.database.seasons_catalog import initialize_seasons_catalog
from app.database.seasons_repository import SeasonsRepository
from app.database.sports_catalog import initialize_sports_catalog
from app.database.sports_repository import SportsRepository


def create_repositories(
    tmp_path: Path,
) -> tuple[
    Path,
    SportsRepository,
    CompetitionsRepository,
    SeasonsRepository,
]:
    database_path = tmp_path / "sports.db"
    Database(database_path).initialize()

    sports_repository = SportsRepository(database_path)
    competitions_repository = CompetitionsRepository(database_path)
    seasons_repository = SeasonsRepository(database_path)

    initialize_sports_catalog(sports_repository)
    initialize_competitions_catalog(
        repository=competitions_repository,
        sports_repository=sports_repository,
    )

    return (
        database_path,
        sports_repository,
        competitions_repository,
        seasons_repository,
    )


def test_initialize_seasons_catalog_creates_reviewed_seasons(
    tmp_path: Path,
) -> None:
    (
        _,
        sports_repository,
        competitions_repository,
        seasons_repository,
    ) = create_repositories(tmp_path)

    seasons = initialize_seasons_catalog(
        repository=seasons_repository,
        competitions_repository=competitions_repository,
        sports_repository=sports_repository,
    )

    assert len(seasons) == 7
    football = sports_repository.get_by_key("football")

    assert football is not None

    premier_league = competitions_repository.get_by_key(
        sport_id=football.id,
        competition_key="premier_league",
    )

    assert premier_league is not None
    bundesliga = competitions_repository.get_by_key(
        sport_id=football.id,
        competition_key="bundesliga",
    )
    assert bundesliga is not None
    championship = competitions_repository.get_by_key(
        sport_id=football.id,
        competition_key="championship",
    )
    assert championship is not None
    second_bundesliga = competitions_repository.get_by_key(
        sport_id=football.id,
        competition_key="second_bundesliga",
    )
    assert second_bundesliga is not None
    dfb_pokal = competitions_repository.get_by_key(
        sport_id=football.id,
        competition_key="dfb_pokal",
    )
    assert dfb_pokal is not None
    oefb_cup = competitions_repository.get_by_key(
        sport_id=football.id,
        competition_key="oefb_cup",
    )
    assert oefb_cup is not None
    nations_league = competitions_repository.get_by_key(
        sport_id=football.id,
        competition_key="uefa_nations_league",
    )
    assert nations_league is not None
    by_competition = {season.competition_id: season for season in seasons}

    premier_league_season = by_competition[premier_league.id]
    assert premier_league_season.season_key == "2026_27"
    assert premier_league_season.name == "2026/27"
    assert premier_league_season.start_date == "2026-08-21"
    assert premier_league_season.end_date == "2027-05-30"
    assert premier_league_season.is_current is True
    assert premier_league_season.metadata is None

    bundesliga_season = by_competition[bundesliga.id]
    assert bundesliga_season.season_key == "2026_27"
    assert bundesliga_season.name == "2026/27"
    assert bundesliga_season.start_date == "2026-08-28"
    assert bundesliga_season.end_date == "2027-05-22"
    assert bundesliga_season.is_current is True
    assert bundesliga_season.metadata is None

    championship_season = by_competition[championship.id]
    assert championship_season.season_key == "2026_27"
    assert championship_season.name == "2026/27"
    assert championship_season.start_date == "2026-08-14"
    assert championship_season.end_date == "2027-05-01"
    assert championship_season.is_current is True
    assert championship_season.metadata is None

    second_bundesliga_season = by_competition[second_bundesliga.id]
    assert second_bundesliga_season.season_key == "2026_27"
    assert second_bundesliga_season.name == "2026/27"
    assert second_bundesliga_season.start_date == "2026-08-07"
    assert second_bundesliga_season.end_date == "2027-05-23"
    assert second_bundesliga_season.is_current is True
    assert second_bundesliga_season.metadata is None

    dfb_pokal_season = by_competition[dfb_pokal.id]
    assert dfb_pokal_season.season_key == "2026_27"
    assert dfb_pokal_season.name == "2026/27"
    assert dfb_pokal_season.start_date == "2026-08-21"
    assert dfb_pokal_season.end_date == "2027-05-29"
    assert dfb_pokal_season.is_current is True
    assert dfb_pokal_season.metadata is None

    oefb_cup_season = by_competition[oefb_cup.id]
    assert oefb_cup_season.season_key == "2026_27"
    assert oefb_cup_season.name == "2026/27"
    assert oefb_cup_season.start_date == "2026-07-01"
    assert oefb_cup_season.end_date == "2027-06-30"
    assert oefb_cup_season.is_current is True
    assert oefb_cup_season.metadata is None

    nations_league_season = by_competition[nations_league.id]
    assert nations_league_season.season_key == "2026_27"
    assert nations_league_season.name == "2026/27 League A group phase"
    assert nations_league_season.start_date == "2026-09-24"
    assert nations_league_season.end_date == "2026-11-17"
    assert nations_league_season.is_current is True


def test_initialize_seasons_catalog_can_run_repeatedly(
    tmp_path: Path,
) -> None:
    (
        database_path,
        sports_repository,
        competitions_repository,
        seasons_repository,
    ) = create_repositories(tmp_path)

    first_result = initialize_seasons_catalog(
        repository=seasons_repository,
        competitions_repository=competitions_repository,
        sports_repository=sports_repository,
    )
    second_result = initialize_seasons_catalog(
        repository=seasons_repository,
        competitions_repository=competitions_repository,
        sports_repository=sports_repository,
    )

    with sqlite3.connect(database_path) as connection:
        season_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM seasons
            WHERE competition_id = ?
              AND season_key = ?
            """,
            (
                first_result[0].competition_id,
                "2026_27",
            ),
        ).fetchone()

    assert season_count == (1,)
    assert [item.id for item in second_result] == [item.id for item in first_result]
    assert [item.created_at for item in second_result] == [
        item.created_at for item in first_result
    ]


def test_initialize_seasons_catalog_restores_master_data(
    tmp_path: Path,
) -> None:
    (
        _,
        sports_repository,
        competitions_repository,
        seasons_repository,
    ) = create_repositories(tmp_path)

    football = sports_repository.get_by_key("football")

    assert football is not None

    premier_league = competitions_repository.get_by_key(
        sport_id=football.id,
        competition_key="premier_league",
    )

    assert premier_league is not None

    seasons_repository.upsert(
        competition_id=premier_league.id,
        season_key="2026_27",
        name="Incorrect name",
        start_date=None,
        end_date=None,
        is_current=False,
        metadata={"incorrect": True},
    )

    initialize_seasons_catalog(
        repository=seasons_repository,
        competitions_repository=competitions_repository,
        sports_repository=sports_repository,
    )

    season = seasons_repository.get_by_key(
        competition_id=premier_league.id,
        season_key="2026_27",
    )

    assert season is not None
    assert season.name == "2026/27"
    assert season.start_date == "2026-08-21"
    assert season.end_date == "2027-05-30"
    assert season.is_current is True
    assert season.metadata is None


def test_initialize_seasons_catalog_requires_premier_league(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "sports.db"
    Database(database_path).initialize()

    sports_repository = SportsRepository(database_path)
    initialize_sports_catalog(sports_repository)

    with pytest.raises(
        RuntimeError,
        match="Required competition not found.*premier_league",
    ):
        initialize_seasons_catalog(
            repository=SeasonsRepository(database_path),
            competitions_repository=CompetitionsRepository(database_path),
            sports_repository=sports_repository,
        )


def test_initialize_seasons_catalog_identifies_missing_bundesliga(
    tmp_path: Path,
) -> None:
    database_path, sports, competitions, seasons = create_repositories(tmp_path)
    football = sports.get_by_key("football")
    assert football is not None
    bundesliga = competitions.get_by_key(football.id, "bundesliga")
    assert bundesliga is not None
    with sqlite3.connect(database_path) as connection:
        connection.execute("DELETE FROM competitions WHERE id = ?", (bundesliga.id,))

    with pytest.raises(
        RuntimeError,
        match="Required competition not found.*bundesliga",
    ):
        initialize_seasons_catalog(seasons, competitions, sports)
