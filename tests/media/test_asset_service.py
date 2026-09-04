from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest
from app.database.database import Database
from app.database.media_assets_repository import MediaAssetsRepository
from app.domain.media_assets import MediaAssetError, MediaOwnerType
from app.media.asset_service import (
    MediaAssetService,
    MediaAssetValidationError,
    MediaImportLimits,
)
from PIL import Image, PngImagePlugin


def create_service(
    tmp_path: Path,
    *,
    limits: MediaImportLimits | None = None,
) -> tuple[MediaAssetService, MediaAssetsRepository, Path]:
    database_path = tmp_path / "sports.db"
    media_root = tmp_path / "media"
    Database(database_path).initialize()
    repository = MediaAssetsRepository(database_path)
    return (
        MediaAssetService(repository, media_root, limits=limits),
        repository,
        media_root,
    )


def create_png(
    path: Path,
    *,
    size: tuple[int, int] = (120, 60),
    color: tuple[int, int, int, int] = (180, 20, 40, 255),
    metadata: bool = False,
) -> None:
    info = PngImagePlugin.PngInfo()
    if metadata:
        info.add_text("private-note", "must be removed")
    Image.new("RGBA", size, color).save(path, format="PNG", pnginfo=info)


def import_project_asset(
    service: MediaAssetService,
    repository: MediaAssetsRepository,
    source_file: Path,
    *,
    asset_key: str = "project.trophy",
):
    return service.import_asset(
        asset_key=asset_key,
        owner=repository.resolve_owner(
            MediaOwnerType.PROJECT,
            "smart_sports_calendar",
        ),
        variant="trophy",
        source_file=source_file,
        source_reference="project-owned synthetic source",
        license_name="MIT",
        permission_reference=None,
        attribution="SMART Sports Calendar",
    )


def test_import_decodes_scales_and_strips_metadata(tmp_path: Path) -> None:
    service, repository, media_root = create_service(tmp_path)
    source_file = tmp_path / "source.png"
    create_png(source_file, metadata=True)

    asset = import_project_asset(service, repository, source_file)
    stored_path = media_root / asset.storage_path

    assert asset.is_approved is False
    assert asset.is_active is False
    assert asset.mime_type == "image/png"
    assert asset.width == 60
    assert asset.height == 60
    assert stored_path.is_file()
    with Image.open(stored_path) as stored:
        stored.load()
        assert stored.format == "PNG"
        assert stored.size == (60, 60)
        assert "private-note" not in stored.info


def test_identical_content_is_stored_once_by_hash(tmp_path: Path) -> None:
    service, repository, media_root = create_service(tmp_path)
    source_file = tmp_path / "source.png"
    create_png(source_file)

    first = import_project_asset(service, repository, source_file)
    second = import_project_asset(
        service,
        repository,
        source_file,
        asset_key="project.final",
    )

    assert first.sha256 == second.sha256
    assert first.storage_path == second.storage_path
    assert len(list(media_root.rglob("*.png"))) == 1


@pytest.mark.parametrize("kind", ["malformed", "unsupported", "oversized"])
def test_unsafe_sources_fail_closed(tmp_path: Path, kind: str) -> None:
    limits = MediaImportLimits(
        maximum_source_bytes=1024,
        maximum_source_width=64,
        maximum_source_height=64,
    )
    service, repository, media_root = create_service(tmp_path, limits=limits)
    source_file = tmp_path / "source.bin"
    if kind == "malformed":
        source_file.write_bytes(b"not an image")
    elif kind == "unsupported":
        Image.new("RGB", (10, 10), "red").save(source_file, format="GIF")
    else:
        create_png(source_file, size=(65, 10))

    with pytest.raises(MediaAssetValidationError):
        import_project_asset(service, repository, source_file)

    assert repository.list(include_inactive=True) == []
    assert not media_root.exists() or list(media_root.rglob("*.png")) == []


def test_source_byte_limit_is_checked_before_decode(tmp_path: Path) -> None:
    service, repository, _ = create_service(
        tmp_path,
        limits=MediaImportLimits(maximum_source_bytes=10),
    )
    source_file = tmp_path / "large.bin"
    source_file.write_bytes(b"x" * 11)

    with pytest.raises(MediaAssetValidationError, match="file size"):
        import_project_asset(service, repository, source_file)


def test_missing_rights_evidence_fails_before_storage(tmp_path: Path) -> None:
    service, repository, media_root = create_service(tmp_path)
    source_file = tmp_path / "source.png"
    create_png(source_file)

    with pytest.raises(MediaAssetValidationError, match="rights evidence"):
        service.import_asset(
            asset_key="project.trophy",
            owner=repository.resolve_owner(
                MediaOwnerType.PROJECT,
                "smart_sports_calendar",
            ),
            variant="trophy",
            source_file=source_file,
            source_reference="synthetic",
            license_name=None,
            permission_reference=None,
            attribution=None,
        )

    assert not media_root.exists()


def test_stable_identity_fails_before_new_content_is_stored(tmp_path: Path) -> None:
    service, repository, media_root = create_service(tmp_path)
    first_source = tmp_path / "first.png"
    second_source = tmp_path / "second.png"
    create_png(first_source, color=(180, 20, 40, 255))
    create_png(second_source, color=(20, 40, 180, 255))
    first = import_project_asset(service, repository, first_source)

    with pytest.raises(MediaAssetError, match="cannot change"):
        service.import_asset(
            asset_key=first.asset_key,
            owner=repository.resolve_owner(
                MediaOwnerType.PROJECT,
                "smart_sports_calendar",
            ),
            variant="final",
            source_file=second_source,
            source_reference="project-owned synthetic source",
            license_name="MIT",
            permission_reference=None,
            attribution="SMART Sports Calendar",
        )

    assert len(list(media_root.rglob("*.png"))) == 1


def test_import_limits_must_be_positive() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        MediaImportLimits(normalized_width=0)


def test_approval_verifies_stored_hash_and_fails_on_corruption(tmp_path: Path) -> None:
    service, repository, media_root = create_service(tmp_path)
    source_file = tmp_path / "source.png"
    create_png(source_file)
    pending = import_project_asset(service, repository, source_file)
    (media_root / pending.storage_path).write_bytes(b"corrupted")

    with pytest.raises(MediaAssetValidationError, match="integrity"):
        service.approve(pending.asset_key, pending.version, "operator")

    assert repository.get_active(pending.asset_key) is None


def test_approval_rejects_traversal_even_for_corrupt_registry_state(
    tmp_path: Path,
) -> None:
    service, repository, _ = create_service(tmp_path)
    source_file = tmp_path / "source.png"
    create_png(source_file)
    pending = import_project_asset(service, repository, source_file)
    mocked_repository = Mock(spec=MediaAssetsRepository)
    mocked_repository.get_version.return_value = replace(
        pending,
        storage_path="../outside.png",
    )
    unsafe_service = MediaAssetService(mocked_repository, tmp_path / "media")

    with pytest.raises(MediaAssetValidationError, match="path is unsafe"):
        unsafe_service.approve(pending.asset_key, pending.version, "operator")

    mocked_repository.approve.assert_not_called()


def test_read_active_content_revalidates_approval_hash_and_size(tmp_path: Path) -> None:
    service, repository, media_root = create_service(tmp_path)
    source_file = tmp_path / "source.png"
    create_png(source_file)
    pending = import_project_asset(service, repository, source_file)

    with pytest.raises(MediaAssetValidationError, match="approved active"):
        service.read_active_content(pending)

    approved = service.approve(pending.asset_key, pending.version, "operator")
    content = service.read_active_content(approved)
    assert content == (media_root / approved.storage_path).read_bytes()

    with pytest.raises(MediaAssetValidationError, match="attachment limits"):
        service.read_active_content(approved, maximum_bytes=len(content) - 1)

    (media_root / approved.storage_path).write_bytes(b"corrupted")
    with pytest.raises(MediaAssetValidationError, match="integrity"):
        service.read_active_content(approved)
