import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.database.media_assets_repository import MediaAsset

MEDIA_SLOTS = ("competition", "home", "away", "final")


class EventAssetAttachmentRepositoryError(RuntimeError):
    pass


@dataclass(frozen=True)
class EventAssetAttachment:
    id: int
    calendar_event_mapping_id: int
    slot: str
    desired_asset_id: int | None
    desired_sha256: str | None
    synchronized_asset_id: int | None
    synchronized_sha256: str | None
    content_id: str | None
    outlook_attachment_id: str | None
    pending_asset_id: int | None
    pending_sha256: str | None
    pending_content_id: str | None
    pending_outlook_attachment_id: str | None
    obsolete_outlook_attachment_id: str | None
    status: str
    attempt_count: int
    last_attempt_at: str | None
    last_synced_at: str | None
    last_error: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class AppliedAttachment:
    asset_id: int
    sha256: str
    content_id: str
    outlook_attachment_id: str


class EventAssetAttachmentsRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def list_for_mapping(self, mapping_id: int) -> list[EventAssetAttachment]:
        self._validate_positive(mapping_id, "Calendar event mapping ID")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM calendar_event_asset_attachments
                WHERE calendar_event_mapping_id = ?
                ORDER BY CASE slot
                    WHEN 'competition' THEN 0
                    WHEN 'home' THEN 1
                    WHEN 'away' THEN 2
                    ELSE 3
                END
                """,
                (mapping_id,),
            ).fetchall()
        return [self._map_row(row) for row in rows]

    def reconcile_desired(
        self,
        mapping_id: int,
        desired: Mapping[str, MediaAsset],
    ) -> list[EventAssetAttachment]:
        self._validate_positive(mapping_id, "Calendar event mapping ID")
        self._validate_desired(desired)
        timestamp = self._timestamp()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            mapping = connection.execute(
                """
                SELECT id, outlook_event_id
                FROM calendar_event_mappings
                WHERE id = ? AND sync_status != 'deleted'
                """,
                (mapping_id,),
            ).fetchone()
            if mapping is None or mapping["outlook_event_id"] is None:
                raise EventAssetAttachmentRepositoryError(
                    "Media attachments require a live Outlook event mapping."
                )
            existing = {
                row["slot"]: row
                for row in connection.execute(
                    """
                    SELECT * FROM calendar_event_asset_attachments
                    WHERE calendar_event_mapping_id = ?
                    """,
                    (mapping_id,),
                ).fetchall()
            }
            for slot in MEDIA_SLOTS:
                asset = desired.get(slot)
                desired_id = None if asset is None else asset.id
                desired_hash = None if asset is None else asset.sha256
                row = existing.get(slot)
                if row is None:
                    if asset is None:
                        continue
                    connection.execute(
                        """
                        INSERT INTO calendar_event_asset_attachments (
                            calendar_event_mapping_id, slot, desired_asset_id,
                            desired_sha256, status, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, 'pending', ?, ?)
                        """,
                        (
                            mapping_id,
                            slot,
                            desired_id,
                            desired_hash,
                            timestamp,
                            timestamp,
                        ),
                    )
                    continue
                if (
                    row["desired_asset_id"] == desired_id
                    and row["desired_sha256"] == desired_hash
                ):
                    continue
                obsolete = row["obsolete_outlook_attachment_id"]
                pending_id = row["pending_outlook_attachment_id"]
                pending_matches = row["pending_sha256"] == desired_hash
                move_pending = pending_id is not None and not pending_matches
                if move_pending and obsolete is not None:
                    raise EventAssetAttachmentRepositoryError(
                        "Multiple obsolete attachments require cleanup."
                    )
                if move_pending and obsolete is None:
                    obsolete = pending_id
                    pending_id = None
                connection.execute(
                    """
                    UPDATE calendar_event_asset_attachments
                    SET desired_asset_id = ?,
                        desired_sha256 = ?,
                        pending_asset_id = CASE
                            WHEN pending_sha256 IS ? THEN pending_asset_id
                            ELSE NULL
                        END,
                        pending_sha256 = CASE
                            WHEN pending_sha256 IS ? THEN pending_sha256
                            ELSE NULL
                        END,
                        pending_content_id = CASE
                            WHEN pending_sha256 IS ? THEN pending_content_id
                            ELSE NULL
                        END,
                        pending_outlook_attachment_id = ?,
                        obsolete_outlook_attachment_id = ?,
                        status = CASE
                            WHEN ? IS NOT NULL THEN 'cleanup_pending'
                            WHEN ? IS synchronized_sha256
                                 AND outlook_attachment_id IS NOT NULL
                                THEN 'synced'
                            WHEN ? IS NULL
                                 AND synchronized_sha256 IS NULL
                                THEN 'synced'
                            ELSE 'pending'
                        END,
                        last_error = NULL,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        desired_id,
                        desired_hash,
                        desired_hash,
                        desired_hash,
                        desired_hash,
                        pending_id,
                        obsolete,
                        obsolete,
                        desired_hash,
                        desired_hash,
                        timestamp,
                        row["id"],
                    ),
                )
        return self.list_for_mapping(mapping_id)

    def prepare_upload(
        self,
        attachment_id: int,
        asset: MediaAsset,
    ) -> EventAssetAttachment:
        self._validate_positive(attachment_id, "Attachment mapping ID")
        timestamp = self._timestamp()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM calendar_event_asset_attachments WHERE id = ?",
                (attachment_id,),
            ).fetchone()
            if row is None:
                raise EventAssetAttachmentRepositoryError(
                    "Attachment mapping was not found."
                )
            if (
                row["desired_asset_id"] != asset.id
                or row["desired_sha256"] != asset.sha256
            ):
                raise EventAssetAttachmentRepositoryError(
                    "Desired media asset changed before upload preparation."
                )
            if row["obsolete_outlook_attachment_id"] is not None:
                return self._map_row(row)
            content_id = (
                row["pending_content_id"]
                if row["pending_sha256"] == asset.sha256
                else None
            ) or f"ssc-{uuid4().hex}@smart-sports-calendar"
            connection.execute(
                """
                UPDATE calendar_event_asset_attachments
                SET pending_asset_id = ?,
                    pending_sha256 = ?,
                    pending_content_id = ?,
                    pending_outlook_attachment_id = CASE
                        WHEN pending_sha256 IS ?
                        THEN pending_outlook_attachment_id
                        ELSE NULL
                    END,
                    status = 'pending',
                    last_error = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    asset.id,
                    asset.sha256,
                    content_id,
                    asset.sha256,
                    timestamp,
                    attachment_id,
                ),
            )
        prepared = self.get_by_id(attachment_id)
        if prepared is None:
            raise EventAssetAttachmentRepositoryError(
                "Attachment mapping disappeared after upload preparation."
            )
        return prepared

    def mark_attempt(self, attachment_id: int) -> EventAssetAttachment:
        timestamp = self._timestamp()
        return self._update_and_get(
            attachment_id,
            """
            UPDATE calendar_event_asset_attachments
            SET attempt_count = attempt_count + 1,
                last_attempt_at = ?,
                last_error = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (timestamp, timestamp, attachment_id),
        )

    def mark_uploaded(
        self,
        attachment_id: int,
        outlook_attachment_id: str,
    ) -> EventAssetAttachment:
        self._validate_remote_id(outlook_attachment_id, "Outlook attachment ID")
        timestamp = self._timestamp()
        return self._update_and_get(
            attachment_id,
            """
            UPDATE calendar_event_asset_attachments
            SET pending_outlook_attachment_id = ?,
                status = 'uploaded',
                last_error = NULL,
                updated_at = ?
            WHERE id = ?
              AND pending_asset_id IS NOT NULL
              AND pending_content_id IS NOT NULL
            """,
            (outlook_attachment_id, timestamp, attachment_id),
        )

    def mark_failed(
        self,
        attachment_id: int,
        error_message: str,
    ) -> EventAssetAttachment:
        safe_error = self._safe_error(error_message)
        timestamp = self._timestamp()
        return self._update_and_get(
            attachment_id,
            """
            UPDATE calendar_event_asset_attachments
            SET status = 'failed',
                last_error = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (safe_error, timestamp, attachment_id),
        )

    def mark_body_refresh_required(self, mapping_id: int) -> None:
        self._validate_positive(mapping_id, "Calendar event mapping ID")
        timestamp = self._timestamp()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE calendar_event_asset_attachments
                SET status = 'failed',
                    last_error = 'Event body requires media refresh.',
                    updated_at = ?
                WHERE calendar_event_mapping_id = ?
                  AND status != 'event_deleted'
                """,
                (timestamp, mapping_id),
            )

    def mark_remote_missing(
        self,
        attachment_id: int,
    ) -> EventAssetAttachment:
        timestamp = self._timestamp()
        return self._update_and_get(
            attachment_id,
            """
            UPDATE calendar_event_asset_attachments
            SET synchronized_asset_id = NULL,
                synchronized_sha256 = NULL,
                content_id = NULL,
                outlook_attachment_id = NULL,
                status = CASE
                    WHEN desired_asset_id IS NULL THEN 'synced'
                    ELSE 'pending'
                END,
                last_error = NULL,
                updated_at = ?
            WHERE id = ?
              AND outlook_attachment_id IS NOT NULL
            """,
            (timestamp, attachment_id),
        )

    def apply_body(
        self,
        mapping_id: int,
        applied: Mapping[str, AppliedAttachment | None],
    ) -> list[EventAssetAttachment]:
        timestamp = self._timestamp()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for slot, target in applied.items():
                self._validate_slot(slot)
                row = connection.execute(
                    """
                    SELECT * FROM calendar_event_asset_attachments
                    WHERE calendar_event_mapping_id = ? AND slot = ?
                    """,
                    (mapping_id, slot),
                ).fetchone()
                if row is None:
                    raise EventAssetAttachmentRepositoryError(
                        "Attachment mapping disappeared before body persistence."
                    )
                target_id = None if target is None else target.outlook_attachment_id
                old_id = row["outlook_attachment_id"]
                obsolete = row["obsolete_outlook_attachment_id"]
                if old_id is not None and old_id != target_id:
                    if obsolete not in {None, old_id}:
                        raise EventAssetAttachmentRepositoryError(
                            "Multiple obsolete attachments require cleanup."
                        )
                    obsolete = old_id
                target_asset_id = None if target is None else target.asset_id
                target_hash = None if target is None else target.sha256
                target_content_id = None if target is None else target.content_id
                clear_pending = (
                    target_id is not None
                    and target_id == row["pending_outlook_attachment_id"]
                )
                connection.execute(
                    """
                    UPDATE calendar_event_asset_attachments
                    SET synchronized_asset_id = ?,
                        synchronized_sha256 = ?,
                        content_id = ?,
                        outlook_attachment_id = ?,
                        pending_asset_id = CASE
                            WHEN ? THEN NULL ELSE pending_asset_id
                        END,
                        pending_sha256 = CASE WHEN ? THEN NULL ELSE pending_sha256 END,
                        pending_content_id = CASE
                            WHEN ? THEN NULL ELSE pending_content_id
                        END,
                        pending_outlook_attachment_id = CASE
                            WHEN ? THEN NULL ELSE pending_outlook_attachment_id
                        END,
                        obsolete_outlook_attachment_id = ?,
                        status = CASE
                            WHEN ? IS NOT NULL THEN 'cleanup_pending'
                            WHEN desired_sha256 IS ? THEN 'synced'
                            ELSE 'pending'
                        END,
                        last_synced_at = ?,
                        last_error = NULL,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        target_asset_id,
                        target_hash,
                        target_content_id,
                        target_id,
                        clear_pending,
                        clear_pending,
                        clear_pending,
                        clear_pending,
                        obsolete,
                        obsolete,
                        target_hash,
                        timestamp,
                        timestamp,
                        row["id"],
                    ),
                )
        return self.list_for_mapping(mapping_id)

    def mark_cleanup_complete(
        self,
        attachment_id: int,
    ) -> EventAssetAttachment:
        timestamp = self._timestamp()
        return self._update_and_get(
            attachment_id,
            """
            UPDATE calendar_event_asset_attachments
            SET obsolete_outlook_attachment_id = NULL,
                status = CASE
                    WHEN desired_sha256 IS synchronized_sha256 THEN 'synced'
                    ELSE 'pending'
                END,
                last_error = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (timestamp, attachment_id),
        )

    def mark_event_deleted(self, mapping_id: int) -> None:
        timestamp = self._timestamp()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE calendar_event_asset_attachments
                SET desired_asset_id = NULL,
                    desired_sha256 = NULL,
                    synchronized_asset_id = NULL,
                    synchronized_sha256 = NULL,
                    content_id = NULL,
                    outlook_attachment_id = NULL,
                    pending_asset_id = NULL,
                    pending_sha256 = NULL,
                    pending_content_id = NULL,
                    pending_outlook_attachment_id = NULL,
                    obsolete_outlook_attachment_id = NULL,
                    status = 'event_deleted',
                    last_error = NULL,
                    updated_at = ?
                WHERE calendar_event_mapping_id = ?
                """,
                (timestamp, mapping_id),
            )

    def get_by_id(self, attachment_id: int) -> EventAssetAttachment | None:
        self._validate_positive(attachment_id, "Attachment mapping ID")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM calendar_event_asset_attachments WHERE id = ?",
                (attachment_id,),
            ).fetchone()
        return None if row is None else self._map_row(row)

    def _update_and_get(
        self,
        attachment_id: int,
        statement: str,
        arguments: tuple[object, ...],
    ) -> EventAssetAttachment:
        self._validate_positive(attachment_id, "Attachment mapping ID")
        with self._connect() as connection:
            cursor = connection.execute(statement, arguments)
        if cursor.rowcount == 0:
            raise EventAssetAttachmentRepositoryError(
                "Attachment mapping update did not affect a row."
            )
        result = self.get_by_id(attachment_id)
        if result is None:
            raise EventAssetAttachmentRepositoryError(
                "Attachment mapping disappeared after update."
            )
        return result

    @staticmethod
    def _map_row(row: sqlite3.Row) -> EventAssetAttachment:
        return EventAssetAttachment(**dict(row))

    @staticmethod
    def _validate_desired(desired: Mapping[str, MediaAsset]) -> None:
        for slot, asset in desired.items():
            EventAssetAttachmentsRepository._validate_slot(slot)
            if not asset.is_approved or not asset.is_active:
                raise EventAssetAttachmentRepositoryError(
                    "Desired media assets must be approved and active."
                )

    @staticmethod
    def _validate_slot(slot: str) -> None:
        if slot not in MEDIA_SLOTS:
            raise EventAssetAttachmentRepositoryError(
                "Unsupported media attachment slot."
            )

    @staticmethod
    def _validate_positive(value: int, label: str) -> None:
        if value < 1:
            raise EventAssetAttachmentRepositoryError(f"{label} must be positive.")

    @staticmethod
    def _validate_remote_id(value: str, label: str) -> None:
        if not value or value != value.strip() or len(value) > 1000:
            raise EventAssetAttachmentRepositoryError(f"{label} is invalid.")

    @staticmethod
    def _safe_error(value: str) -> str:
        normalized = " ".join(value.split()).strip()
        return (normalized or "Optional media operation failed.")[:500]

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(UTC).isoformat()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection
