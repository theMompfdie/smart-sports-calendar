from pathlib import Path

from app.database.data_sources_repository import DataSourcesRepository
from app.database.database import Database


def create_repository(
    tmp_path: Path,
) -> DataSourcesRepository:
    database_path = tmp_path / "sports.db"
    Database(database_path).initialize()

    return DataSourcesRepository(database_path)


def test_get_by_key_returns_none_for_unknown_source(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path)

    data_source = repository.get_by_key("unknown")

    assert data_source is None


def test_upsert_creates_data_source(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path)

    data_source = repository.upsert(
        source_key="football_data",
        name="football-data.org",
        base_url="https://api.football-data.org/v4",
    )

    assert data_source.id > 0
    assert data_source.source_key == "football_data"
    assert data_source.name == "football-data.org"
    assert data_source.base_url == "https://api.football-data.org/v4"
    assert data_source.is_active is True
    assert data_source.metadata is None
    assert data_source.created_at
    assert data_source.updated_at


def test_get_by_key_returns_existing_data_source(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path)

    created_source = repository.upsert(
        source_key="football_data",
        name="football-data.org",
    )

    loaded_source = repository.get_by_key("football_data")

    assert loaded_source == created_source


def test_upsert_updates_existing_data_source(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path)

    created_source = repository.upsert(
        source_key="football_data",
        name="Football Data",
        base_url="https://old.example.com",
    )

    updated_source = repository.upsert(
        source_key="football_data",
        name="football-data.org",
        base_url="https://api.football-data.org/v4",
        is_active=False,
    )

    assert updated_source.id == created_source.id
    assert updated_source.name == "football-data.org"
    assert updated_source.base_url == "https://api.football-data.org/v4"
    assert updated_source.is_active is False
    assert updated_source.created_at == created_source.created_at
    assert updated_source.updated_at >= created_source.updated_at


def test_upsert_serializes_and_loads_metadata(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path)

    data_source = repository.upsert(
        source_key="football_data",
        name="football-data.org",
        metadata={
            "rate_limit_per_minute": 10,
            "authentication": "api_key",
        },
    )

    assert data_source.metadata == {
        "rate_limit_per_minute": 10,
        "authentication": "api_key",
    }


def test_upsert_can_clear_optional_values(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path)

    repository.upsert(
        source_key="football_data",
        name="football-data.org",
        base_url="https://api.football-data.org/v4",
        metadata={"authentication": "api_key"},
    )

    updated_source = repository.upsert(
        source_key="football_data",
        name="football-data.org",
        base_url=None,
        metadata=None,
    )

    assert updated_source.base_url is None
    assert updated_source.metadata is None


def test_get_all_returns_sources_ordered_by_name(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path)

    repository.upsert(
        source_key="second_source",
        name="Zulu Sports",
    )
    repository.upsert(
        source_key="first_source",
        name="Alpha Sports",
    )

    data_sources = repository.get_all()

    assert len(data_sources) == 2
    assert data_sources[0].source_key == "first_source"
    assert data_sources[1].source_key == "second_source"


def test_get_all_returns_empty_list_without_sources(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path)

    data_sources = repository.get_all()

    assert data_sources == []


def test_get_all_can_filter_active_sources(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path)

    repository.upsert(
        source_key="active_source",
        name="Active Source",
        is_active=True,
    )
    repository.upsert(
        source_key="inactive_source",
        name="Inactive Source",
        is_active=False,
    )

    data_sources = repository.get_all(active_only=True)

    assert len(data_sources) == 1
    assert data_sources[0].source_key == "active_source"
    assert data_sources[0].is_active is True


def test_upsert_does_not_create_duplicate_source_keys(
    tmp_path: Path,
) -> None:
    repository = create_repository(tmp_path)

    first_source = repository.upsert(
        source_key="football_data",
        name="Football Data",
    )
    second_source = repository.upsert(
        source_key="football_data",
        name="football-data.org",
    )

    data_sources = repository.get_all()

    assert len(data_sources) == 1
    assert second_source.id == first_source.id
    assert second_source.name == "football-data.org"
