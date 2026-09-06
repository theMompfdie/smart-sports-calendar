import sqlite3
from contextlib import closing
from hashlib import sha256
from pathlib import Path

from app.database.sports_repository import SportsRepository

from tests.catalog_support import CatalogInitializer


def database_dump(path: Path) -> list[str]:
    with closing(sqlite3.connect(path)) as connection:
        return list(connection.iterdump())


def test_template_copy_preserves_complete_schema_and_catalog(
    tmp_path: Path,
    catalog_template: Path,
    initialize_test_catalog: CatalogInitializer,
) -> None:
    database_path = tmp_path / "nested" / "sports.db"
    initialize_test_catalog(database_path)

    assert database_dump(database_path) == database_dump(catalog_template)
    with closing(sqlite3.connect(database_path)) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_mutating_one_copy_cannot_change_other_copies_or_template(
    tmp_path: Path,
    catalog_template: Path,
    initialize_test_catalog: CatalogInitializer,
) -> None:
    template_digest = sha256(catalog_template.read_bytes()).digest()
    first = tmp_path / "first.db"
    second = tmp_path / "second.db"
    third = tmp_path / "third.db"
    initialize_test_catalog(first)
    initialize_test_catalog(second)

    SportsRepository(first).upsert("test_only", "Test only", "T")
    with closing(sqlite3.connect(first)) as connection:
        connection.execute("CREATE TABLE test_only (value TEXT)")
        connection.commit()

    initialize_test_catalog(third)
    assert SportsRepository(first).get_by_key("test_only") is not None
    assert database_dump(second) == database_dump(catalog_template)
    assert database_dump(third) == database_dump(catalog_template)
    assert sha256(catalog_template.read_bytes()).digest() == template_digest


def test_reinitialization_preserves_existing_rows_and_reapplies_catalog(
    tmp_path: Path,
    initialize_test_catalog: CatalogInitializer,
) -> None:
    database_path = tmp_path / "restart.db"
    initialize_test_catalog(database_path)
    repository = SportsRepository(database_path)
    football = repository.get_by_key("football")
    assert football is not None
    repository.upsert("football", "Changed name", football.icon)
    custom = repository.upsert("test_only", "Keep on restart", "T")

    initialize_test_catalog(database_path)

    restored = repository.get_by_key("football")
    assert restored is not None
    assert restored.id == football.id
    assert restored.name == football.name
    assert repository.get_by_key("test_only") == custom
