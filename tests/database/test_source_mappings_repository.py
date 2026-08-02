import sqlite3
from pathlib import Path

import pytest
from app.database.data_sources_repository import DataSourcesRepository
from app.database.database import Database
from app.database.source_mappings_repository import SourceMappingsRepository


def create_repository(
    tmp_path: Path,
) -> tuple[int, SourceMappingsRepository]:
    database_path = tmp_path / "sports.db"
    Database(database_path).initialize()

    data_source = DataSourcesRepository(database_path).upsert(
        source_key="football_data",
        name="football-data.org",
        base_url="https://api.football-data.org/v4",
    )

    return (
        data_source.id,
        SourceMappingsRepository(database_path),
    )


def test_get_by_external_id_returns_none_for_unknown_mapping(
    tmp_path: Path,
) -> None:
    source_id, repository = create_repository(tmp_path)

    mapping = repository.get_by_external_id(
        source_id=source_id,
        object_type="competition",
        external_id="PL",
    )

    assert mapping is None


def test_get_by_internal_id_returns_none_for_unknown_mapping(
    tmp_path: Path,
) -> None:
    source_id, repository = create_repository(tmp_path)

    mapping = repository.get_by_internal_id(
        source_id=source_id,
        object_type="competition",
        internal_id=999999,
    )

    assert mapping is None


def test_upsert_creates_source_mapping(
    tmp_path: Path,
) -> None:
    source_id, repository = create_repository(tmp_path)

    mapping = repository.upsert(
        source_id=source_id,
        object_type="competition",
        internal_id=42,
        external_id="PL",
        source_url="https://api.football-data.org/v4/competitions/PL",
    )

    assert mapping.id > 0
    assert mapping.source_id == source_id
    assert mapping.object_type == "competition"
    assert mapping.internal_id == 42
    assert mapping.external_id == "PL"
    assert mapping.source_url == "https://api.football-data.org/v4/competitions/PL"
    assert mapping.metadata is None
    assert mapping.created_at
    assert mapping.updated_at


def test_get_by_external_id_returns_existing_mapping(
    tmp_path: Path,
) -> None:
    source_id, repository = create_repository(tmp_path)

    created_mapping = repository.upsert(
        source_id=source_id,
        object_type="competition",
        internal_id=42,
        external_id="PL",
    )

    loaded_mapping = repository.get_by_external_id(
        source_id=source_id,
        object_type="competition",
        external_id="PL",
    )

    assert loaded_mapping == created_mapping


def test_get_by_internal_id_returns_existing_mapping(
    tmp_path: Path,
) -> None:
    source_id, repository = create_repository(tmp_path)

    created_mapping = repository.upsert(
        source_id=source_id,
        object_type="competition",
        internal_id=42,
        external_id="PL",
    )

    loaded_mapping = repository.get_by_internal_id(
        source_id=source_id,
        object_type="competition",
        internal_id=42,
    )

    assert loaded_mapping == created_mapping


def test_upsert_updates_existing_external_mapping(
    tmp_path: Path,
) -> None:
    source_id, repository = create_repository(tmp_path)

    created_mapping = repository.upsert(
        source_id=source_id,
        object_type="competition",
        internal_id=42,
        external_id="PL",
        source_url="https://old.example.com/PL",
        metadata={"version": 1},
    )

    updated_mapping = repository.upsert(
        source_id=source_id,
        object_type="competition",
        internal_id=84,
        external_id="PL",
        source_url="https://api.football-data.org/v4/competitions/PL",
        metadata={"version": 2},
    )

    assert updated_mapping.id == created_mapping.id
    assert updated_mapping.internal_id == 84
    assert (
        updated_mapping.source_url == "https://api.football-data.org/v4/competitions/PL"
    )
    assert updated_mapping.metadata == {"version": 2}
    assert updated_mapping.created_at == created_mapping.created_at
    assert updated_mapping.updated_at >= created_mapping.updated_at


def test_upsert_does_not_create_duplicate_external_mapping(
    tmp_path: Path,
) -> None:
    source_id, repository = create_repository(tmp_path)

    first_mapping = repository.upsert(
        source_id=source_id,
        object_type="competition",
        internal_id=42,
        external_id="PL",
    )
    second_mapping = repository.upsert(
        source_id=source_id,
        object_type="competition",
        internal_id=84,
        external_id="PL",
    )

    mappings = repository.get_for_source(source_id)

    assert len(mappings) == 1
    assert second_mapping.id == first_mapping.id
    assert second_mapping.internal_id == 84


def test_upsert_serializes_and_loads_metadata(
    tmp_path: Path,
) -> None:
    source_id, repository = create_repository(tmp_path)

    mapping = repository.upsert(
        source_id=source_id,
        object_type="competition",
        internal_id=42,
        external_id="PL",
        metadata={
            "provider_name": "Premier League",
            "country": "England",
        },
    )

    assert mapping.metadata == {
        "provider_name": "Premier League",
        "country": "England",
    }


def test_upsert_can_clear_optional_values(
    tmp_path: Path,
) -> None:
    source_id, repository = create_repository(tmp_path)

    repository.upsert(
        source_id=source_id,
        object_type="competition",
        internal_id=42,
        external_id="PL",
        source_url="https://api.football-data.org/v4/competitions/PL",
        metadata={"country": "England"},
    )

    updated_mapping = repository.upsert(
        source_id=source_id,
        object_type="competition",
        internal_id=42,
        external_id="PL",
        source_url=None,
        metadata=None,
    )

    assert updated_mapping.source_url is None
    assert updated_mapping.metadata is None


def test_get_for_source_returns_mappings_in_defined_order(
    tmp_path: Path,
) -> None:
    source_id, repository = create_repository(tmp_path)

    repository.upsert(
        source_id=source_id,
        object_type="participant",
        internal_id=20,
        external_id="57",
    )
    repository.upsert(
        source_id=source_id,
        object_type="competition",
        internal_id=30,
        external_id="PL",
    )
    repository.upsert(
        source_id=source_id,
        object_type="competition",
        internal_id=10,
        external_id="CL",
    )

    mappings = repository.get_for_source(source_id)

    assert len(mappings) == 3
    assert mappings[0].object_type == "competition"
    assert mappings[0].internal_id == 10
    assert mappings[1].object_type == "competition"
    assert mappings[1].internal_id == 30
    assert mappings[2].object_type == "participant"
    assert mappings[2].internal_id == 20


def test_get_for_source_can_filter_by_object_type(
    tmp_path: Path,
) -> None:
    source_id, repository = create_repository(tmp_path)

    repository.upsert(
        source_id=source_id,
        object_type="competition",
        internal_id=42,
        external_id="PL",
    )
    repository.upsert(
        source_id=source_id,
        object_type="participant",
        internal_id=57,
        external_id="57",
    )

    mappings = repository.get_for_source(
        source_id=source_id,
        object_type="competition",
    )

    assert len(mappings) == 1
    assert mappings[0].object_type == "competition"
    assert mappings[0].external_id == "PL"


def test_get_for_source_returns_empty_list_for_unknown_source(
    tmp_path: Path,
) -> None:
    _, repository = create_repository(tmp_path)

    mappings = repository.get_for_source(999999)

    assert mappings == []


def test_same_external_id_can_be_used_for_different_object_types(
    tmp_path: Path,
) -> None:
    source_id, repository = create_repository(tmp_path)

    competition_mapping = repository.upsert(
        source_id=source_id,
        object_type="competition",
        internal_id=42,
        external_id="57",
    )
    participant_mapping = repository.upsert(
        source_id=source_id,
        object_type="participant",
        internal_id=57,
        external_id="57",
    )

    mappings = repository.get_for_source(source_id)

    assert len(mappings) == 2
    assert competition_mapping.id != participant_mapping.id


def test_upsert_rejects_unknown_source(
    tmp_path: Path,
) -> None:
    _, repository = create_repository(tmp_path)

    with pytest.raises(sqlite3.IntegrityError):
        repository.upsert(
            source_id=999999,
            object_type="competition",
            internal_id=42,
            external_id="PL",
        )


def test_upsert_rejects_duplicate_internal_mapping(
    tmp_path: Path,
) -> None:
    source_id, repository = create_repository(tmp_path)

    repository.upsert(
        source_id=source_id,
        object_type="competition",
        internal_id=42,
        external_id="PL",
    )

    with pytest.raises(sqlite3.IntegrityError):
        repository.upsert(
            source_id=source_id,
            object_type="competition",
            internal_id=42,
            external_id="PREMIER_LEAGUE",
        )


def test_delete_removes_existing_mapping(
    tmp_path: Path,
) -> None:
    source_id, repository = create_repository(tmp_path)

    repository.upsert(
        source_id=source_id,
        object_type="competition",
        internal_id=42,
        external_id="PL",
    )

    deleted = repository.delete(
        source_id=source_id,
        object_type="competition",
        external_id="PL",
    )

    assert deleted is True
    assert (
        repository.get_by_external_id(
            source_id=source_id,
            object_type="competition",
            external_id="PL",
        )
        is None
    )


def test_delete_returns_false_for_unknown_mapping(
    tmp_path: Path,
) -> None:
    source_id, repository = create_repository(tmp_path)

    deleted = repository.delete(
        source_id=source_id,
        object_type="competition",
        external_id="UNKNOWN",
    )

    assert deleted is False
