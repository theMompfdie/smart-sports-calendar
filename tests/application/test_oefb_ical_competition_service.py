import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.application.oefb_ical_competition_service import (
    OEFB_ICAL_ATTRIBUTION,
    OefbIcalCompetitionService,
)
from app.database.competitions_repository import CompetitionsRepository
from app.database.data_sources_repository import DataSourcesRepository
from app.database.database import Database
from app.database.participants_repository import ParticipantsRepository
from app.database.season_participants_repository import SeasonParticipantsRepository
from app.database.seasons_repository import SeasonsRepository
from app.database.source_mappings_repository import SourceMappingsRepository
from app.database.sports_repository import SportsRepository
from app.domain.competition_lifecycle import CompetitionFormat
from app.providers.oefb_ical.exceptions import (
    OefbIcalIntegrityError,
    OefbIcalResolutionError,
)
from app.providers.oefb_ical.models import parse_snapshot
from app.providers.oefb_ical.profiles import OEFB_CUP_PROFILE
from app.providers.oefb_ical.team_mappings import OefbIcalTeamMapping

from tests.catalog_support import CatalogInitializer
from tests.providers.oefb_ical.support import (
    FETCHED_AT,
    LAST_MODIFIED,
    calendar_payload,
    settings,
)


class SnapshotAdapter:
    def __init__(self, payload: bytes) -> None:
        self._snapshot = parse_snapshot(
            payload,
            fetched_at_utc=FETCHED_AT,
            request_attempts=2,
            last_modified=LAST_MODIFIED,
        )

    def fetch_snapshot(self):
        return self._snapshot


def create_service(
    tmp_path: Path,
    *,
    payload: bytes | None = None,
    mapping_count: int = 64,
):
    database_path = tmp_path / "sports.db"
    Database(database_path).initialize()
    sports = SportsRepository(database_path)
    competitions = CompetitionsRepository(database_path)
    seasons = SeasonsRepository(database_path)
    participants = ParticipantsRepository(database_path)
    memberships = SeasonParticipantsRepository(database_path)
    sources = DataSourcesRepository(database_path)
    source_mappings = SourceMappingsRepository(database_path)
    football = sports.upsert("football", "Football")
    competition = competitions.upsert(
        sport_id=football.id,
        competition_key=OEFB_CUP_PROFILE.canonical_competition_key,
        name=OEFB_CUP_PROFILE.competition_name,
        short_name="ÖFB Cup",
        country_code="AT",
        competition_type=CompetitionFormat.KNOCKOUT_CUP,
    )
    seasons.upsert(
        competition_id=competition.id,
        season_key=OEFB_CUP_PROFILE.canonical_season_key,
        name="2026/27",
        start_date=OEFB_CUP_PROFILE.season_start_date.isoformat(),
        end_date=OEFB_CUP_PROFILE.season_end_date.isoformat(),
        is_current=True,
    )
    mappings: dict[int, OefbIcalTeamMapping] = {}
    for index in range(mapping_count):
        provider_id = 2000 + index
        participant_key = f"oefb-team-{provider_id}"
        participants.upsert(
            sport_id=football.id,
            participant_key=participant_key,
            participant_type="team",
            name=f"Canonical Team {provider_id}",
            country_code="AT",
        )
        mappings[provider_id] = OefbIcalTeamMapping(
            participant_key=participant_key,
            provider_name=f"Provider Team {provider_id}",
        )
    service = OefbIcalCompetitionService(
        settings=settings(),
        adapter=SnapshotAdapter(payload or calendar_payload()),
        sports_repository=sports,
        competitions_repository=competitions,
        seasons_repository=seasons,
        participants_repository=participants,
        season_participants_repository=memberships,
        data_sources_repository=sources,
        source_mappings_repository=source_mappings,
        team_mappings=mappings,
    )
    return service, database_path, sources, source_mappings


def test_service_normalizes_permanent_partial_snapshot_and_catalog(
    tmp_path: Path,
) -> None:
    service, database_path, _, _ = create_service(tmp_path)

    batch = service.fetch_normalized_snapshot()

    assert batch.competition_format is CompetitionFormat.KNOCKOUT_CUP
    assert len(batch.fixtures) == 1
    fixture = batch.fixtures[0]
    assert fixture.external_id == "1000000"
    assert fixture.title == "Canonical Team 2000 vs Canonical Team 2001"
    assert fixture.round_name == "round-1"
    assert fixture.sequence_number == 1
    assert fixture.metadata == {
        "official_url": "https://www.oefb.at/cup/Spiel/1000000?synthetic=true"
    }
    with sqlite3.connect(database_path) as connection:
        source = connection.execute(
            "SELECT base_url, metadata_json FROM data_sources "
            "WHERE source_key = 'oefb_ical'"
        ).fetchone()
        mapping_counts = connection.execute(
            "SELECT object_type, COUNT(*) FROM source_mappings "
            "GROUP BY object_type ORDER BY object_type"
        ).fetchall()
        membership_count = connection.execute(
            "SELECT COUNT(*) FROM season_participants"
        ).fetchone()[0]
    assert source is not None
    assert source[0] == "https://www.fussballoesterreich.at"
    assert "opaque-test-token" not in source[1]
    assert OEFB_ICAL_ATTRIBUTION in source[1]
    assert mapping_counts == [
        ("competition", 1),
        ("participant", 64),
        ("season", 1),
    ]
    assert membership_count == 64


def test_service_excludes_events_outside_current_season(tmp_path: Path) -> None:
    historical = calendar_payload().replace(
        b"DTSTART:20260828T180000Z",
        b"DTSTART:20250828T180000Z",
    )
    current = calendar_payload().replace(b"UID:1000000", b"UID:1000001")
    combined = historical.replace(b"END:VCALENDAR\r\n", b"")
    current_event = current.split(b"BEGIN:VEVENT", 1)[1].split(b"END:VCALENDAR", 1)[0]
    payload = combined + b"BEGIN:VEVENT" + current_event + b"END:VCALENDAR\r\n"
    service, _, _, _ = create_service(tmp_path, payload=payload)

    batch = service.fetch_normalized_snapshot()

    assert [fixture.external_id for fixture in batch.fixtures] == ["1000001"]


def test_service_requires_exactly_64_reviewed_participants(tmp_path: Path) -> None:
    service, _, _, _ = create_service(tmp_path, mapping_count=63)

    with pytest.raises(OefbIcalResolutionError, match="exactly 64 participants"):
        service.fetch_normalized_snapshot()


def test_service_rejects_unknown_provider_participant(tmp_path: Path) -> None:
    payload = calendar_payload().replace(b"X-HOMENR:2000", b"X-HOMENR:9999")
    service, _, _, _ = create_service(tmp_path, payload=payload)

    with pytest.raises(OefbIcalIntegrityError, match="unknown participant"):
        service.fetch_normalized_snapshot()


def test_service_rejects_current_season_uid_shrink(tmp_path: Path) -> None:
    service, _, sources, mappings = create_service(tmp_path)
    service.fetch_normalized_snapshot()
    source = sources.get_by_key("oefb_ical")
    assert source is not None
    mappings.upsert(
        source_id=source.id,
        object_type="event",
        internal_id=999,
        external_id="1999999",
        metadata={"observed_for_test": True},
    )

    with pytest.raises(OefbIcalIntegrityError, match="UID set shrank"):
        service.fetch_normalized_snapshot()


def test_service_rejects_invalid_canonical_season_dates(tmp_path: Path) -> None:
    service, database_path, _, _ = create_service(tmp_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE seasons SET end_date = ? WHERE season_key = ?",
            ("2027-05-31", OEFB_CUP_PROFILE.canonical_season_key),
        )

    with pytest.raises(OefbIcalResolutionError, match="season dates are invalid"):
        service.fetch_normalized_snapshot()


def test_service_keeps_snapshot_observation_timestamp(tmp_path: Path) -> None:
    service, _, _, _ = create_service(tmp_path)

    batch = service.fetch_normalized_snapshot()

    assert batch.fetched_at_utc == datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


def test_service_resolves_reviewed_production_catalog_mapping(
    tmp_path: Path, *, initialize_test_catalog: CatalogInitializer
) -> None:
    database_path = tmp_path / "reviewed-catalog.db"
    initialize_test_catalog(database_path)
    sports = SportsRepository(database_path)
    competitions = CompetitionsRepository(database_path)
    seasons = SeasonsRepository(database_path)
    participants = ParticipantsRepository(database_path)
    memberships = SeasonParticipantsRepository(database_path)
    payload = (
        calendar_payload()
        .replace(b"X-HOMENR:2000", b"X-HOMENR:1027")
        .replace(b"X-AWAYNR:2001", b"X-AWAYNR:1031")
        .replace(b"SUMMARY:Home 0 : Away 0", b"SUMMARY:Wiener Viktoria : FAC Wien")
    )
    service = OefbIcalCompetitionService(
        settings=settings(),
        adapter=SnapshotAdapter(payload),
        sports_repository=sports,
        competitions_repository=competitions,
        seasons_repository=seasons,
        participants_repository=participants,
        season_participants_repository=memberships,
        data_sources_repository=DataSourcesRepository(database_path),
        source_mappings_repository=SourceMappingsRepository(database_path),
    )

    batch = service.fetch_normalized_snapshot()

    assert len(batch.fixtures) == 1
    assert batch.fixtures[0].title == "Wiener Viktoria vs FAC Wien"
