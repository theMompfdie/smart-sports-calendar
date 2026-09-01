import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.database.competitions_repository import CompetitionsRepository
from app.database.database import Database
from app.database.media_assets_repository import (
    MediaAssetRepositoryError,
    MediaAssetsRepository,
)
from app.database.participants_repository import ParticipantsRepository
from app.database.sports_repository import SportsRepository
from app.domain.media_assets import MediaAssetWrite, MediaOwnerType

NOW = datetime(2026, 9, 1, 15, 0, tzinfo=UTC)


@pytest.fixture
def repository(tmp_path: Path) -> MediaAssetsRepository:
    database_path = tmp_path / "sports.db"
    Database(database_path).initialize()
    sport = SportsRepository(database_path).upsert("football", "Football")
    CompetitionsRepository(database_path).upsert(
        sport.id,
        "premier_league",
        "Premier League",
    )
    ParticipantsRepository(database_path).upsert(
        sport.id,
        "manchester_united",
        "team",
        "Manchester United",
    )
    return MediaAssetsRepository(database_path, clock=lambda: NOW)


def write_for(
    repository: MediaAssetsRepository,
    *,
    digest: str = "a" * 64,
    source_reference: str = "operator-reviewed-source",
) -> MediaAssetWrite:
    return MediaAssetWrite(
        asset_key="team.manchester_united.logo",
        owner=repository.resolve_owner(
            MediaOwnerType.PARTICIPANT,
            "manchester_united",
        ),
        variant="logo",
        mime_type="image/png",
        width=60,
        height=60,
        byte_size=200,
        sha256=digest,
        storage_path=f"assets/{digest[:2]}/{digest}.png",
        source_reference=source_reference,
        license_name=None,
        permission_reference="private-rights-record-001",
        attribution="Used with permission",
    )


def test_resolves_every_canonical_owner_type(repository: MediaAssetsRepository) -> None:
    project = repository.resolve_owner(MediaOwnerType.PROJECT, "smart_sports_calendar")
    sport = repository.resolve_owner(MediaOwnerType.SPORT, "football")
    competition = repository.resolve_owner(
        MediaOwnerType.COMPETITION,
        "premier_league",
    )
    participant = repository.resolve_owner(
        MediaOwnerType.PARTICIPANT,
        "manchester_united",
    )

    assert repository.owner_key_for(project) == "smart_sports_calendar"
    assert repository.owner_key_for(sport) == "football"
    assert repository.owner_key_for(competition) == "premier_league"
    assert repository.owner_key_for(participant) == "manchester_united"


def test_pending_import_is_inactive_and_idempotent(
    repository: MediaAssetsRepository,
) -> None:
    write = write_for(repository)

    first = repository.create_pending(write)
    second = repository.create_pending(write)

    assert second == first
    assert first.version == 1
    assert first.is_approved is False
    assert first.is_active is False
    assert repository.get_active(first.asset_key) is None
    assert repository.list() == []
    assert repository.list(include_inactive=True) == [first]


def test_approval_and_replacement_retain_version_history(
    repository: MediaAssetsRepository,
) -> None:
    first = repository.create_pending(write_for(repository))
    approved_first = repository.approve(first.asset_key, first.version, "operator")
    replacement = repository.create_pending(
        write_for(
            repository,
            digest="b" * 64,
            source_reference="replacement-source",
        )
    )

    assert approved_first.is_active is True
    assert replacement.version == 2
    assert replacement.is_active is False
    assert repository.get_active(first.asset_key) == approved_first

    approved_replacement = repository.approve(
        replacement.asset_key,
        replacement.version,
        "reviewer",
    )
    superseded = repository.get_version(first.asset_key, first.version)

    assert approved_replacement.is_active is True
    assert approved_replacement.approved_by == "reviewer"
    assert superseded is not None
    assert superseded.is_approved is True
    assert superseded.is_active is False
    assert superseded.superseded_by_id == approved_replacement.id
    assert len(repository.list(include_inactive=True)) == 2


def test_owner_variant_lookup_returns_one_active_asset_and_rejects_ambiguity(
    repository: MediaAssetsRepository,
) -> None:
    first = repository.create_pending(write_for(repository))
    approved = repository.approve(first.asset_key, first.version, "operator")

    assert (
        repository.get_active_for_owner_variant(first.owner, first.variant) == approved
    )

    second_write = MediaAssetWrite(
        **{
            **write_for(
                repository,
                digest="b" * 64,
                source_reference="second-family",
            ).__dict__,
            "asset_key": "team.manchester_united.alternate",
        }
    )
    second = repository.create_pending(second_write)
    repository.approve(second.asset_key, second.version, "operator")

    with pytest.raises(MediaAssetRepositoryError, match="Multiple active"):
        repository.get_active_for_owner_variant(first.owner, first.variant)


def test_disable_preserves_approval_and_audit_history(
    repository: MediaAssetsRepository,
) -> None:
    pending = repository.create_pending(write_for(repository))
    repository.approve(pending.asset_key, pending.version, "operator")

    disabled = repository.disable(pending.asset_key)

    assert disabled.is_approved is True
    assert disabled.is_active is False
    assert disabled.deactivated_at == NOW.isoformat()
    assert repository.get_active(pending.asset_key) is None


def test_replacement_cannot_change_stable_owner_or_variant(
    repository: MediaAssetsRepository,
) -> None:
    repository.create_pending(write_for(repository))
    original = write_for(repository, digest="b" * 64)
    changed = MediaAssetWrite(
        **{
            **original.__dict__,
            "owner": repository.resolve_owner(MediaOwnerType.SPORT, "football"),
        }
    )

    with pytest.raises(MediaAssetRepositoryError, match="cannot change"):
        repository.create_pending(changed)


def test_missing_rights_or_unsafe_path_fails_closed(
    repository: MediaAssetsRepository,
) -> None:
    valid = write_for(repository)
    without_rights = MediaAssetWrite(
        **{
            **valid.__dict__,
            "license_name": None,
            "permission_reference": None,
        }
    )
    unsafe_path = MediaAssetWrite(
        **{**valid.__dict__, "storage_path": "../outside.png"}
    )

    with pytest.raises(MediaAssetRepositoryError, match="rights evidence"):
        repository.create_pending(without_rights)
    with pytest.raises(MediaAssetRepositoryError, match="path is unsafe"):
        repository.create_pending(unsafe_path)


def test_database_rejects_activating_unapproved_asset(
    repository: MediaAssetsRepository,
) -> None:
    pending = repository.create_pending(write_for(repository))
    with (
        sqlite3.connect(repository.database_path) as connection,
        pytest.raises(sqlite3.IntegrityError),
    ):
        connection.execute(
            "UPDATE media_assets SET is_active = 1 WHERE id = ?",
            (pending.id,),
        )
