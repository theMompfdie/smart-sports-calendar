import hashlib
import os
import tempfile
import warnings
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from app.database.media_assets_repository import MediaAsset, MediaAssetsRepository
from app.domain.media_assets import MediaAssetError, MediaAssetOwner, MediaAssetWrite


class MediaAssetValidationError(MediaAssetError):
    pass


@dataclass(frozen=True)
class MediaImportLimits:
    maximum_source_bytes: int = 10 * 1024 * 1024
    maximum_source_width: int = 4096
    maximum_source_height: int = 4096
    normalized_width: int = 60
    normalized_height: int = 60
    maximum_normalized_bytes: int = 1024 * 1024

    def __post_init__(self) -> None:
        if any(
            value <= 0
            for value in (
                self.maximum_source_bytes,
                self.maximum_source_width,
                self.maximum_source_height,
                self.normalized_width,
                self.normalized_height,
                self.maximum_normalized_bytes,
            )
        ):
            raise ValueError("Media import limits must be positive.")


class MediaAssetService:
    _SUPPORTED_FORMATS = {"JPEG", "PNG"}

    def __init__(
        self,
        repository: MediaAssetsRepository,
        media_root: Path,
        *,
        limits: MediaImportLimits | None = None,
    ) -> None:
        self._repository = repository
        self._media_root = media_root
        self._limits = limits or MediaImportLimits()

    def import_asset(
        self,
        *,
        asset_key: str,
        owner: MediaAssetOwner,
        variant: str,
        source_file: Path,
        source_reference: str,
        license_name: str | None,
        permission_reference: str | None,
        attribution: str | None,
    ) -> MediaAsset:
        if license_name is None and permission_reference is None:
            raise MediaAssetValidationError("Media asset rights evidence is required.")
        normalized = self._normalize(source_file)
        digest = hashlib.sha256(normalized).hexdigest()
        relative_path = Path("assets") / digest[:2] / f"{digest}.png"
        write = MediaAssetWrite(
            asset_key=asset_key,
            owner=owner,
            variant=variant,
            mime_type="image/png",
            width=self._limits.normalized_width,
            height=self._limits.normalized_height,
            byte_size=len(normalized),
            sha256=digest,
            storage_path=relative_path.as_posix(),
            source_reference=source_reference,
            license_name=license_name,
            permission_reference=permission_reference,
            attribution=attribution,
        )
        self._repository.validate_pending(write)
        self._store(relative_path, normalized, digest)
        return self._repository.create_pending(write)

    def approve(self, asset_key: str, version: int, reviewer: str) -> MediaAsset:
        asset = self._repository.get_version(asset_key, version)
        if asset is None:
            raise MediaAssetValidationError("Media asset version was not found.")
        self._verify_stored_asset(asset)
        return self._repository.approve(asset_key, version, reviewer)

    def disable(self, asset_key: str) -> MediaAsset:
        return self._repository.disable(asset_key)

    def _normalize(self, source_file: Path) -> bytes:
        try:
            with source_file.open("rb") as source:
                source.seek(0, os.SEEK_END)
                source_size = source.tell()
                source.seek(0)
                if source_size <= 0 or source_size > self._limits.maximum_source_bytes:
                    raise MediaAssetValidationError(
                        "Media source file size is outside the allowed range."
                    )
                with warnings.catch_warnings():
                    warnings.simplefilter("error", Image.DecompressionBombWarning)
                    with Image.open(source) as image:
                        if image.format not in self._SUPPORTED_FORMATS:
                            raise MediaAssetValidationError(
                                "Media source format is unsupported."
                            )
                        if getattr(image, "n_frames", 1) != 1:
                            raise MediaAssetValidationError(
                                "Animated media sources are unsupported."
                            )
                        width, height = image.size
                        if (
                            width <= 0
                            or height <= 0
                            or width > self._limits.maximum_source_width
                            or height > self._limits.maximum_source_height
                        ):
                            raise MediaAssetValidationError(
                                "Media source dimensions are outside the allowed range."
                            )
                        image.load()
                        decoded = ImageOps.exif_transpose(image).convert("RGBA")
        except MediaAssetValidationError:
            raise
        except (Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
            raise MediaAssetValidationError(
                "Media source exceeds safe decompression limits."
            ) from error
        except (OSError, UnidentifiedImageError, ValueError) as error:
            raise MediaAssetValidationError(
                "Media source could not be decoded safely."
            ) from error

        decoded.thumbnail(
            (self._limits.normalized_width, self._limits.normalized_height),
            Image.Resampling.LANCZOS,
        )
        canvas = Image.new(
            "RGBA",
            (self._limits.normalized_width, self._limits.normalized_height),
            (0, 0, 0, 0),
        )
        offset = (
            (self._limits.normalized_width - decoded.width) // 2,
            (self._limits.normalized_height - decoded.height) // 2,
        )
        canvas.alpha_composite(decoded, offset)
        output = BytesIO()
        canvas.save(output, format="PNG", compress_level=9, optimize=False)
        normalized = output.getvalue()
        if not normalized or len(normalized) > self._limits.maximum_normalized_bytes:
            raise MediaAssetValidationError(
                "Normalized media asset size is outside the allowed range."
            )
        return normalized

    def _store(self, relative_path: Path, content: bytes, digest: str) -> None:
        root = self._resolved_root()
        target = self._resolve_contained(root, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target = self._resolve_contained(root, relative_path)
        if target.is_symlink():
            raise MediaAssetValidationError("Media storage target is unsafe.")
        if target.exists():
            if not target.is_file() or self._hash_file(target) != digest:
                raise MediaAssetValidationError(
                    "Existing media storage content failed integrity validation."
                )
            return
        descriptor, temporary_name = tempfile.mkstemp(
            dir=target.parent,
            prefix=".media-",
            suffix=".tmp",
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as temporary:
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
            temporary_path.replace(target)
        finally:
            temporary_path.unlink(missing_ok=True)
        if self._hash_file(target) != digest:
            target.unlink(missing_ok=True)
            raise MediaAssetValidationError(
                "Stored media asset failed integrity validation."
            )

    def _verify_stored_asset(self, asset: MediaAsset) -> None:
        root = self._resolved_root()
        target = self._resolve_contained(root, Path(asset.storage_path))
        if (
            target.is_symlink()
            or not target.is_file()
            or target.stat().st_size != asset.byte_size
            or self._hash_file(target) != asset.sha256
        ):
            raise MediaAssetValidationError(
                "Stored media asset failed integrity validation."
            )

    def _resolved_root(self) -> Path:
        try:
            self._media_root.mkdir(parents=True, exist_ok=True)
            return self._media_root.resolve(strict=True)
        except OSError as error:
            raise MediaAssetValidationError(
                "Media storage root is unavailable."
            ) from error

    @staticmethod
    def _resolve_contained(root: Path, relative_path: Path) -> Path:
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise MediaAssetValidationError("Media storage path is unsafe.")
        candidate = (root / relative_path).resolve(strict=False)
        if not candidate.is_relative_to(root):
            raise MediaAssetValidationError("Media storage path is unsafe.")
        return candidate

    @staticmethod
    def _hash_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stored:
            for chunk in iter(lambda: stored.read(64 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
