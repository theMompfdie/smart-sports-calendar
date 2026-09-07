"""Build real catalog data once and copy it into isolated test databases."""

import sqlite3
from collections.abc import Callable
from contextlib import closing
from pathlib import Path

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

type CatalogInitializer = Callable[[Path], None]


def build_catalog(database_path: Path) -> None:
    """Use the production migrations and catalog initializers without shortcuts."""
    Database(database_path).initialize()
    sports = SportsRepository(database_path)
    competitions = CompetitionsRepository(database_path)
    seasons = SeasonsRepository(database_path)
    participants = ParticipantsRepository(database_path)
    memberships = SeasonParticipantsRepository(database_path)
    initialize_sports_catalog(sports)
    initialize_competitions_catalog(competitions, sports)
    initialize_seasons_catalog(seasons, competitions, sports)
    initialize_participants_catalog(
        participants, memberships, sports, competitions, seasons
    )


def initialize_from_template(template: Path, database_path: Path) -> None:
    """Seed a fresh database; keep the real reinitialization path on restart."""
    if database_path.exists():
        build_catalog(database_path)
        return

    database_path.parent.mkdir(parents=True, exist_ok=True)
    with (
        closing(sqlite3.connect(f"{template.as_uri()}?mode=ro", uri=True)) as source,
        closing(sqlite3.connect(database_path)) as destination,
    ):
        source.backup(destination)
