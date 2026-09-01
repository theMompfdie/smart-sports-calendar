import re
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.domain.media_assets import (
    MediaAssetError,
    MediaAssetOwner,
    MediaAssetWrite,
    MediaOwnerType,
)

_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,127}$")
_VARIANT_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class MediaAssetRepositoryError(MediaAssetError):
    pass


class MediaAssetNotFoundError(MediaAssetRepositoryError):
    pass


@dataclass(frozen=True)
class MediaAsset:
    id: int
    asset_key: str
    version: int
    owner: MediaAssetOwner
    variant: str
    mime_type: str
    width: int
    height: int
    byte_size: int
    sha256: str
    storage_path: str
    source_reference: str
    license_name: str | None
    permission_reference: str | None
    attribution: str | None
    is_approved: bool
    approved_by: str | None
    approved_at: str | None
    is_active: bool
    deactivated_at: str | None
    superseded_by_id: int | None
    created_at: str
    updated_at: str


def _utc_now() -> datetime:
    return datetime.now(UTC)


class MediaAssetsRepository:
    def __init__(
        self,
        database_path: Path,
        *,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.database_path = database_path
        self._clock = clock

    def resolve_owner(
        self,
        owner_type: MediaOwnerType,
        owner_key: str,
    ) -> MediaAssetOwner:
        owner_type = MediaOwnerType(owner_type)
        self._validate_key(owner_key, "Media owner key")
        if owner_type is MediaOwnerType.PROJECT:
            return MediaAssetOwner(owner_type, project_key=owner_key)
        table, key_column, id_field = {
            MediaOwnerType.SPORT: ("sports", "sport_key", "sport_id"),
            MediaOwnerType.COMPETITION: (
                "competitions",
                "competition_key",
                "competition_id",
            ),
            MediaOwnerType.PARTICIPANT: (
                "participants",
                "participant_key",
                "participant_id",
            ),
        }[owner_type]
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT id FROM {table} WHERE {key_column} = ? ORDER BY id LIMIT 2",
                (owner_key,),
            ).fetchall()
        if not rows:
            raise MediaAssetNotFoundError(
                f"Unknown canonical {owner_type.value} media owner key."
            )
        if len(rows) > 1:
            raise MediaAssetRepositoryError(
                f"Ambiguous canonical {owner_type.value} media owner key."
            )
        return MediaAssetOwner(owner_type, **{id_field: rows[0]["id"]})

    def owner_key_for(self, owner: MediaAssetOwner) -> str:
        if owner.owner_type is MediaOwnerType.PROJECT:
            assert owner.project_key is not None
            return owner.project_key
        table, key_column, identifier = {
            MediaOwnerType.SPORT: ("sports", "sport_key", owner.sport_id),
            MediaOwnerType.COMPETITION: (
                "competitions",
                "competition_key",
                owner.competition_id,
            ),
            MediaOwnerType.PARTICIPANT: (
                "participants",
                "participant_key",
                owner.participant_id,
            ),
        }[owner.owner_type]
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT {key_column} FROM {table} WHERE id = ?",
                (identifier,),
            ).fetchone()
        if row is None:
            raise MediaAssetRepositoryError("Canonical media owner disappeared.")
        return str(row[key_column])

    def create_pending(self, write: MediaAssetWrite) -> MediaAsset:
        self._validate_write(write)
        timestamp = self._timestamp()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                rows = connection.execute(
                    "SELECT * FROM media_assets WHERE asset_key = ? ORDER BY version",
                    (write.asset_key,),
                ).fetchall()
                if rows:
                    self._validate_stable_identity(rows[0], write)
                    matching = next(
                        (
                            row
                            for row in reversed(rows)
                            if self._matches_import(row, write)
                        ),
                        None,
                    )
                    if matching is not None:
                        return self._map_row(matching)
                    version = int(rows[-1]["version"]) + 1
                else:
                    version = 1
                cursor = connection.execute(
                    """
                    INSERT INTO media_assets (
                        asset_key, version, owner_type, project_key, sport_id,
                        competition_id, participant_id, variant, mime_type,
                        width, height, byte_size, sha256, storage_path,
                        source_reference, license_name, permission_reference,
                        attribution, is_approved, is_active, created_at, updated_at
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        0, 0, ?, ?
                    )
                    """,
                    (
                        write.asset_key,
                        version,
                        write.owner.owner_type.value,
                        write.owner.project_key,
                        write.owner.sport_id,
                        write.owner.competition_id,
                        write.owner.participant_id,
                        write.variant,
                        write.mime_type,
                        write.width,
                        write.height,
                        write.byte_size,
                        write.sha256,
                        write.storage_path,
                        write.source_reference,
                        write.license_name,
                        write.permission_reference,
                        write.attribution,
                        timestamp,
                        timestamp,
                    ),
                )
                asset_id = cursor.lastrowid
                if asset_id is None:
                    raise MediaAssetRepositoryError("Media asset could not be created.")
                asset = self._get_by_id(connection, asset_id)
                if asset is None:
                    raise MediaAssetRepositoryError(
                        "Media asset could not be loaded after import."
                    )
                return asset
        except sqlite3.IntegrityError as error:
            raise MediaAssetRepositoryError(
                "Media asset violates a database constraint."
            ) from error

    def validate_pending(self, write: MediaAssetWrite) -> None:
        """Validate a pending import before its normalized bytes are persisted."""
        self._validate_write(write)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM media_assets
                WHERE asset_key = ?
                ORDER BY version
                LIMIT 1
                """,
                (write.asset_key,),
            ).fetchone()
        if row is not None:
            self._validate_stable_identity(row, write)

    def approve(self, asset_key: str, version: int, reviewer: str) -> MediaAsset:
        self._validate_key(asset_key, "Media asset key")
        self._validate_text(reviewer, "Reviewer", maximum=200)
        if version < 1:
            raise MediaAssetRepositoryError("Media asset version must be positive.")
        timestamp = self._timestamp()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            target = self._select_version(connection, asset_key, version)
            if target is None:
                raise MediaAssetNotFoundError("Media asset version was not found.")
            if bool(target["is_active"]):
                asset = self._get_by_id(connection, target["id"])
                assert asset is not None
                return asset
            connection.execute(
                """
                UPDATE media_assets
                SET is_active = 0,
                    deactivated_at = ?,
                    superseded_by_id = ?,
                    updated_at = ?
                WHERE asset_key = ? AND is_active = 1 AND id != ?
                """,
                (timestamp, target["id"], timestamp, asset_key, target["id"]),
            )
            connection.execute(
                """
                UPDATE media_assets
                SET is_approved = 1,
                    approved_by = COALESCE(approved_by, ?),
                    approved_at = COALESCE(approved_at, ?),
                    is_active = 1,
                    deactivated_at = NULL,
                    superseded_by_id = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (reviewer, timestamp, timestamp, target["id"]),
            )
            asset = self._get_by_id(connection, target["id"])
            if asset is None:
                raise MediaAssetRepositoryError(
                    "Media asset could not be loaded after approval."
                )
            return asset

    def disable(self, asset_key: str) -> MediaAsset:
        self._validate_key(asset_key, "Media asset key")
        timestamp = self._timestamp()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM media_assets WHERE asset_key = ? AND is_active = 1",
                (asset_key,),
            ).fetchone()
            if row is None:
                raise MediaAssetNotFoundError("Active media asset was not found.")
            connection.execute(
                """
                UPDATE media_assets
                SET is_active = 0,
                    deactivated_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (timestamp, timestamp, row["id"]),
            )
            asset = self._get_by_id(connection, row["id"])
            assert asset is not None
            return asset

    def get_active(self, asset_key: str) -> MediaAsset | None:
        self._validate_key(asset_key, "Media asset key")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM media_assets WHERE asset_key = ? AND is_active = 1",
                (asset_key,),
            ).fetchone()
        return None if row is None else self._map_row(row)

    def get_version(self, asset_key: str, version: int) -> MediaAsset | None:
        self._validate_key(asset_key, "Media asset key")
        if version < 1:
            raise MediaAssetRepositoryError("Media asset version must be positive.")
        with self._connect() as connection:
            row = self._select_version(connection, asset_key, version)
        return None if row is None else self._map_row(row)

    def list(self, *, include_inactive: bool = False) -> list[MediaAsset]:
        query = "SELECT * FROM media_assets"
        if not include_inactive:
            query += " WHERE is_active = 1"
        query += " ORDER BY asset_key, version"
        with self._connect() as connection:
            rows = connection.execute(query).fetchall()
        return [self._map_row(row) for row in rows]

    @staticmethod
    def _select_version(
        connection: sqlite3.Connection,
        asset_key: str,
        version: int,
    ) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM media_assets WHERE asset_key = ? AND version = ?",
            (asset_key, version),
        ).fetchone()

    @classmethod
    def _get_by_id(
        cls,
        connection: sqlite3.Connection,
        asset_id: int,
    ) -> MediaAsset | None:
        row = connection.execute(
            "SELECT * FROM media_assets WHERE id = ?",
            (asset_id,),
        ).fetchone()
        return None if row is None else cls._map_row(row)

    @staticmethod
    def _map_row(row: sqlite3.Row) -> MediaAsset:
        return MediaAsset(
            id=row["id"],
            asset_key=row["asset_key"],
            version=row["version"],
            owner=MediaAssetOwner(
                MediaOwnerType(row["owner_type"]),
                project_key=row["project_key"],
                sport_id=row["sport_id"],
                competition_id=row["competition_id"],
                participant_id=row["participant_id"],
            ),
            variant=row["variant"],
            mime_type=row["mime_type"],
            width=row["width"],
            height=row["height"],
            byte_size=row["byte_size"],
            sha256=row["sha256"],
            storage_path=row["storage_path"],
            source_reference=row["source_reference"],
            license_name=row["license_name"],
            permission_reference=row["permission_reference"],
            attribution=row["attribution"],
            is_approved=bool(row["is_approved"]),
            approved_by=row["approved_by"],
            approved_at=row["approved_at"],
            is_active=bool(row["is_active"]),
            deactivated_at=row["deactivated_at"],
            superseded_by_id=row["superseded_by_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @classmethod
    def _validate_write(cls, write: MediaAssetWrite) -> None:
        cls._validate_key(write.asset_key, "Media asset key")
        if not _VARIANT_PATTERN.fullmatch(write.variant):
            raise MediaAssetRepositoryError("Media asset variant is invalid.")
        if write.mime_type != "image/png":
            raise MediaAssetRepositoryError("Stored media assets must use PNG.")
        if write.width <= 0 or write.height <= 0 or write.byte_size <= 0:
            raise MediaAssetRepositoryError(
                "Media asset dimensions and size must be positive."
            )
        if not _SHA256_PATTERN.fullmatch(write.sha256):
            raise MediaAssetRepositoryError("Media asset SHA-256 is invalid.")
        storage_path = Path(write.storage_path)
        if (
            storage_path.is_absolute()
            or ".." in storage_path.parts
            or "\\" in write.storage_path
            or ":" in write.storage_path
        ):
            raise MediaAssetRepositoryError("Media asset storage path is unsafe.")
        cls._validate_text(write.source_reference, "Source reference", maximum=1000)
        if write.license_name is None and write.permission_reference is None:
            raise MediaAssetRepositoryError("Media asset rights evidence is required.")
        if write.license_name is not None:
            cls._validate_text(write.license_name, "License name", maximum=200)
        if write.permission_reference is not None:
            cls._validate_text(
                write.permission_reference,
                "Permission reference",
                maximum=1000,
            )
        if write.attribution is not None:
            cls._validate_text(write.attribution, "Attribution", maximum=500)

    @staticmethod
    def _validate_stable_identity(row: sqlite3.Row, write: MediaAssetWrite) -> None:
        actual = (
            row["owner_type"],
            row["project_key"],
            row["sport_id"],
            row["competition_id"],
            row["participant_id"],
            row["variant"],
        )
        expected = (
            write.owner.owner_type.value,
            write.owner.project_key,
            write.owner.sport_id,
            write.owner.competition_id,
            write.owner.participant_id,
            write.variant,
        )
        if actual != expected:
            raise MediaAssetRepositoryError(
                "Media asset key owner and variant cannot change across versions."
            )

    @staticmethod
    def _matches_import(row: sqlite3.Row, write: MediaAssetWrite) -> bool:
        return (
            row["sha256"],
            row["source_reference"],
            row["license_name"],
            row["permission_reference"],
            row["attribution"],
        ) == (
            write.sha256,
            write.source_reference,
            write.license_name,
            write.permission_reference,
            write.attribution,
        )

    @staticmethod
    def _validate_key(value: str, label: str) -> None:
        if not _KEY_PATTERN.fullmatch(value):
            raise MediaAssetRepositoryError(f"{label} is invalid.")

    @staticmethod
    def _validate_text(value: str, label: str, *, maximum: int) -> None:
        if not value or value != value.strip() or len(value) > maximum:
            raise MediaAssetRepositoryError(f"{label} is invalid.")

    def _timestamp(self) -> str:
        value = self._clock()
        if value.tzinfo is None:
            raise MediaAssetRepositoryError("Media asset clock must be timezone-aware.")
        return value.astimezone(UTC).isoformat()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection
