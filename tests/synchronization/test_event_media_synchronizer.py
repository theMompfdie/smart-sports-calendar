from dataclasses import dataclass
from pathlib import Path

import pytest
from app.database.calendar_event_mappings_repository import (
    CalendarEventMapping,
    CalendarEventMappingsRepository,
)
from app.database.competitions_repository import CompetitionsRepository
from app.database.database import Database
from app.database.event_asset_attachments_repository import (
    EventAssetAttachmentsRepository,
)
from app.database.event_participants_repository import EventParticipantsRepository
from app.database.media_assets_repository import MediaAssetsRepository
from app.database.participants_repository import ParticipantsRepository
from app.database.sports_events_repository import SportsEventsRepository
from app.database.sports_repository import SportsRepository
from app.database.synchronization_query_repository import (
    SynchronizationEvent,
    SynchronizationQueryRepository,
)
from app.domain.media_assets import MediaOwnerType
from app.graph.client import OutlookAttachmentReference, OutlookEventReference
from app.media.asset_service import MediaAssetService
from app.media.event_asset_selector import EventAssetSelector
from app.synchronization.event_media_synchronizer import EventMediaSynchronizer
from app.synchronization.outlook_event_payload_builder import OutlookEventPayloadBuilder
from PIL import Image


class RecordingGraph:
    def __init__(self) -> None:
        self.attachments: list[OutlookAttachmentReference] = []
        self.uploads: list[str] = []
        self.updates: list[object] = []
        self.deletions: list[str] = []
        self.upload_error: Exception | None = None
        self.update_error: Exception | None = None

    def list_event_attachments(
        self,
        calendar_id: str,
        event_id: str,
    ) -> tuple[OutlookAttachmentReference, ...]:
        return tuple(self.attachments)

    def create_inline_attachment(
        self,
        calendar_id: str,
        event_id: str,
        *,
        name: str,
        content_id: str,
        content: bytes,
    ) -> OutlookAttachmentReference:
        if self.upload_error is not None:
            raise self.upload_error
        reference = OutlookAttachmentReference(
            f"attachment-{len(self.uploads) + 1}",
            content_id,
            name,
        )
        self.uploads.append(content_id)
        self.attachments.append(reference)
        return reference

    def update_event(self, *, calendar_id: str, event_id: str, payload: object):
        if self.update_error is not None:
            raise self.update_error
        self.updates.append(payload)
        return OutlookEventReference(event_id)

    def delete_event_attachment(
        self,
        calendar_id: str,
        event_id: str,
        attachment_id: str,
    ) -> None:
        self.deletions.append(attachment_id)
        self.attachments = [
            attachment
            for attachment in self.attachments
            if attachment.id != attachment_id
        ]


@dataclass(frozen=True)
class Harness:
    event: SynchronizationEvent
    mapping: CalendarEventMapping
    assets: MediaAssetsRepository
    asset_service: MediaAssetService
    attachments: EventAssetAttachmentsRepository
    synchronizer: EventMediaSynchronizer
    graph: RecordingGraph
    home_key: str


def _import_home_asset(harness: Harness, source: Path, color: str):
    Image.new("RGBA", (60, 60), color).save(source, format="PNG")
    pending = harness.asset_service.import_asset(
        asset_key=harness.home_key,
        owner=harness.assets.resolve_owner(MediaOwnerType.PARTICIPANT, "home"),
        variant="logo",
        source_file=source,
        source_reference=f"synthetic-{color}",
        license_name="MIT",
        permission_reference=None,
        attribution=None,
    )
    return harness.asset_service.approve(pending.asset_key, pending.version, "operator")


def _harness(tmp_path: Path) -> Harness:
    database_path = tmp_path / "sports.db"
    media_root = tmp_path / "media"
    Database(database_path).initialize()
    sport = SportsRepository(database_path).upsert("football", "Football")
    competition = CompetitionsRepository(database_path).upsert(
        sport.id,
        "test_league",
        "Test League",
    )
    participants = ParticipantsRepository(database_path)
    home = participants.upsert(sport.id, "home", "team", "Home")
    away = participants.upsert(sport.id, "away", "team", "Away")
    event = SportsEventsRepository(database_path).upsert(
        sport_id=sport.id,
        competition_id=competition.id,
        event_key="home-away",
        event_type="match",
        title="Home vs Away",
        stage="Regular season",
        start_time="2026-09-02T18:00:00+00:00",
        timezone="UTC",
        status="confirmed",
    )
    assignments = EventParticipantsRepository(database_path)
    assignments.upsert(event.id, home.id, "home", 1)
    assignments.upsert(event.id, away.id, "away", 2)
    mappings = CalendarEventMappingsRepository(database_path)
    pending_mapping = mappings.create_pending(event.id, "calendar-1")
    mapping = mappings.mark_synced(
        pending_mapping.id,
        "outlook-event-1",
        None,
        "a" * 64,
        event.sync_revision,
        pending_mapping.presentation_revision,
    )
    assert mapping is not None
    aggregate = SynchronizationQueryRepository(database_path).get_by_event_id(
        event.id,
        mapping.calendar_id,
    )
    assert aggregate is not None
    assets = MediaAssetsRepository(database_path)
    asset_service = MediaAssetService(assets, media_root)
    attachments = EventAssetAttachmentsRepository(database_path)
    graph = RecordingGraph()
    synchronizer = EventMediaSynchronizer(
        selector=EventAssetSelector(assets),
        asset_service=asset_service,
        attachments_repository=attachments,
        payload_builder=OutlookEventPayloadBuilder(),
        graph_client=graph,  # type: ignore[arg-type]
    )
    return Harness(
        aggregate,
        mapping,
        assets,
        asset_service,
        attachments,
        synchronizer,
        graph,
        "team.home.logo",
    )


def test_media_reconciliation_is_idempotent_and_replaces_without_orphans(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    _import_home_asset(harness, tmp_path / "first.png", "red")

    harness.synchronizer.reconcile(harness.event, harness.mapping)
    first = harness.attachments.list_for_mapping(harness.mapping.id)[0]
    assert first.status == "synced"
    assert len(harness.graph.uploads) == 1
    assert len(harness.graph.updates) == 1
    assert "cid:" in harness.graph.updates[0].body  # type: ignore[union-attr]

    harness.synchronizer.reconcile(harness.event, harness.mapping)
    assert len(harness.graph.uploads) == 1
    assert len(harness.graph.updates) == 1

    _import_home_asset(harness, tmp_path / "replacement.png", "blue")
    harness.synchronizer.reconcile(harness.event, harness.mapping)
    replaced = harness.attachments.list_for_mapping(harness.mapping.id)[0]
    assert replaced.status == "synced"
    assert replaced.outlook_attachment_id == "attachment-2"
    assert harness.graph.deletions == ["attachment-1"]
    assert [item.id for item in harness.graph.attachments] == ["attachment-2"]


def test_core_write_without_selected_media_does_not_add_redundant_patch(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)

    harness.synchronizer.reconcile(
        harness.event,
        harness.mapping,
        core_event_written=True,
    )

    assert harness.graph.uploads == []
    assert harness.graph.updates == []


def test_upload_failure_keeps_text_event_and_persists_retryable_state(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    _import_home_asset(harness, tmp_path / "first.png", "red")
    harness.graph.upload_error = RuntimeError("secret-bearing provider failure")

    harness.synchronizer.reconcile(harness.event, harness.mapping)

    state = harness.attachments.list_for_mapping(harness.mapping.id)[0]
    assert state.status == "failed"
    assert state.last_error == "RuntimeError"
    assert harness.graph.updates == []


def test_restart_recovers_uploaded_attachment_by_content_id(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    asset = _import_home_asset(harness, tmp_path / "first.png", "red")
    state = harness.attachments.reconcile_desired(
        harness.mapping.id,
        {"home": asset},
    )[0]
    prepared = harness.attachments.prepare_upload(state.id, asset)
    assert prepared.pending_content_id is not None
    harness.graph.attachments.append(
        OutlookAttachmentReference(
            "recovered-attachment",
            prepared.pending_content_id,
            "recovered.png",
        )
    )

    harness.synchronizer.reconcile(harness.event, harness.mapping)

    synchronized = harness.attachments.list_for_mapping(harness.mapping.id)[0]
    assert synchronized.status == "synced"
    assert synchronized.outlook_attachment_id == "recovered-attachment"
    assert harness.graph.uploads == []
    assert len(harness.graph.updates) == 1


def test_body_patch_failure_reuses_uploaded_attachment_on_retry(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    _import_home_asset(harness, tmp_path / "first.png", "red")
    harness.graph.update_error = RuntimeError("temporary body failure")

    with pytest.raises(RuntimeError, match="temporary body failure"):
        harness.synchronizer.reconcile(harness.event, harness.mapping)

    failed = harness.attachments.list_for_mapping(harness.mapping.id)[0]
    assert failed.status == "failed"
    assert failed.pending_outlook_attachment_id == "attachment-1"
    harness.graph.update_error = None
    harness.synchronizer.reconcile(harness.event, harness.mapping)

    synchronized = harness.attachments.list_for_mapping(harness.mapping.id)[0]
    assert synchronized.status == "synced"
    assert synchronized.outlook_attachment_id == "attachment-1"
    assert len(harness.graph.uploads) == 1
    assert len(harness.graph.updates) == 1


def test_failed_image_restore_after_core_write_remains_actionable(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    _import_home_asset(harness, tmp_path / "first.png", "red")
    harness.synchronizer.reconcile(harness.event, harness.mapping)
    harness.graph.update_error = RuntimeError("temporary restore failure")

    with pytest.raises(RuntimeError, match="temporary restore failure"):
        harness.synchronizer.reconcile(
            harness.event,
            harness.mapping,
            core_event_written=True,
        )

    failed = harness.attachments.list_for_mapping(harness.mapping.id)[0]
    assert failed.status == "failed"
    harness.graph.update_error = None
    harness.synchronizer.reconcile(harness.event, harness.mapping)

    recovered = harness.attachments.list_for_mapping(harness.mapping.id)[0]
    assert recovered.status == "synced"
    assert len(harness.graph.uploads) == 1
    assert len(harness.graph.updates) == 2
