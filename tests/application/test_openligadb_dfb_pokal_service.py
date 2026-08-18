import sqlite3
from pathlib import Path

import pytest
from app.application.openligadb_dfb_pokal_service import (
    OPENLIGADB_ATTRIBUTION,
    OpenLigaDBDFBPokalService,
)
from app.config.settings import OpenLigaDBSettings
from app.database.competitions_catalog import initialize_competitions_catalog
from app.database.competitions_repository import CompetitionsRepository
from app.database.data_sources_repository import DataSourcesRepository
from app.database.database import Database
from app.database.participants_catalog import initialize_participants_catalog
from app.database.participants_repository import ParticipantsRepository
from app.database.season_participants_repository import SeasonParticipantsRepository
from app.database.seasons_catalog import initialize_seasons_catalog
from app.database.seasons_repository import SeasonsRepository
from app.database.source_mappings_repository import SourceMappingsRepository
from app.database.sports_catalog import initialize_sports_catalog
from app.database.sports_repository import SportsRepository
from app.domain.competition_lifecycle import CompetitionFormat
from app.providers.openligadb.exceptions import OpenLigaDBIntegrityError
from app.providers.openligadb.models import parse_snapshot
from app.providers.openligadb.profiles import DFB_POKAL_PROFILE

from tests.providers.openligadb.support import FETCHED_AT, payloads


class SnapshotAdapter:
    profile = DFB_POKAL_PROFILE

    def __init__(self, snapshot) -> None:
        self._snapshot = snapshot

    def fetch_snapshot(self):
        return self._snapshot


def create_service(tmp_path: Path, *, changed_name: bool = False):
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
    initialize_participants_catalog(
        participants, memberships, sports, competitions, seasons
    )
    raw_payloads = payloads()
    if changed_name:
        raw_payloads[2][0]["team1"]["teamName"] = "Unreviewed name"
    snapshot = parse_snapshot(
        *raw_payloads,
        profile=DFB_POKAL_PROFILE,
        fetched_at_utc=FETCHED_AT,
        request_attempts=3,
    )
    return (
        OpenLigaDBDFBPokalService(
            settings=OpenLigaDBSettings(enabled=True),
            adapter=SnapshotAdapter(snapshot),
            sports_repository=sports,
            competitions_repository=competitions,
            seasons_repository=seasons,
            participants_repository=participants,
            season_participants_repository=memberships,
            data_sources_repository=DataSourcesRepository(database_path),
            source_mappings_repository=SourceMappingsRepository(database_path),
        ),
        database_path,
    )


def test_service_normalizes_partial_dfb_pokal_snapshot_and_mappings(
    tmp_path: Path,
) -> None:
    service, database_path = create_service(tmp_path)

    batch = service.fetch_normalized_snapshot()

    assert batch.competition_format is CompetitionFormat.KNOCKOUT_CUP
    assert len(batch.fixtures) == 1
    fixture = batch.fixtures[0]
    assert fixture.title == "SC St. Tönis vs Eintracht Frankfurt"
    assert fixture.stage == "knockout"
    assert fixture.round_name == "round-1"
    assert fixture.sequence_number == 1
    assert fixture.metadata == {
        "provider_group_id": "101",
        "provider_group_order_id": "1",
    }
    with sqlite3.connect(database_path) as connection:
        source = connection.execute(
            "SELECT metadata_json FROM data_sources WHERE source_key = 'openligadb'"
        ).fetchone()
        mappings = connection.execute(
            "SELECT object_type, external_id FROM source_mappings ORDER BY object_type"
        ).fetchall()
    assert source is not None
    assert OPENLIGADB_ATTRIBUTION in source[0]
    assert mappings == [
        ("competition", "4945"),
        ("participant", "91"),
        ("participant", "5712"),
        ("season", "4945:2026"),
    ]


def test_service_fails_closed_on_changed_provider_identity(tmp_path: Path) -> None:
    service, _ = create_service(tmp_path, changed_name=True)

    with pytest.raises(OpenLigaDBIntegrityError, match="reviewed mapping"):
        service.fetch_normalized_snapshot()
