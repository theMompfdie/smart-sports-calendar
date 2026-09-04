from pathlib import Path

from app.database.calendar_event_mappings_repository import (
    CalendarEventMappingsRepository,
)
from app.database.database import Database
from app.database.event_asset_attachments_repository import (
    AppliedAttachment,
    EventAssetAttachmentsRepository,
)
from app.database.event_participants_repository import EventParticipantsRepository
from app.database.media_assets_repository import MediaAssetsRepository
from app.database.participants_repository import ParticipantsRepository
from app.database.sports_events_repository import SportsEventsRepository
from app.database.sports_repository import SportsRepository
from app.domain.media_assets import MediaAssetWrite, MediaOwnerType


def _approved_asset(
    database_path: Path,
    *,
    digest: str,
    source: str,
):
    repository = MediaAssetsRepository(database_path)
    owner = repository.resolve_owner(MediaOwnerType.PARTICIPANT, "home_team")
    pending = repository.create_pending(
        MediaAssetWrite(
            asset_key="team.home.logo",
            owner=owner,
            variant="logo",
            mime_type="image/png",
            width=60,
            height=60,
            byte_size=128,
            sha256=digest,
            storage_path=f"assets/{digest[:2]}/{digest}.png",
            source_reference=source,
            permission_reference="operator-rights-record",
        )
    )
    return repository.approve(pending.asset_key, pending.version, "operator")


def _setup(database_path: Path):
    Database(database_path).initialize()
    sport = SportsRepository(database_path).upsert("football", "Football")
    participant = ParticipantsRepository(database_path).upsert(
        sport.id,
        "home_team",
        "team",
        "Home Team",
    )
    event = SportsEventsRepository(database_path).upsert(
        sport_id=sport.id,
        event_key="test-match",
        event_type="match",
        title="Home vs Away",
        start_time="2026-09-01T18:00:00+00:00",
        timezone="UTC",
        status="confirmed",
    )
    EventParticipantsRepository(database_path).upsert(
        event.id,
        participant.id,
        "home",
        1,
    )
    mappings = CalendarEventMappingsRepository(database_path)
    pending = mappings.create_pending(event.id, "calendar-1")
    mapping = mappings.mark_synced(
        pending.id,
        "outlook-event-1",
        None,
        "a" * 64,
        event.sync_revision,
        pending.presentation_revision,
    )
    assert mapping is not None
    return mapping


def test_attachment_state_survives_upload_body_switch_and_cleanup(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "sports.db"
    mapping = _setup(database_path)
    asset = _approved_asset(database_path, digest="b" * 64, source="first")
    repository = EventAssetAttachmentsRepository(database_path)

    state = repository.reconcile_desired(mapping.id, {"home": asset})[0]
    prepared = repository.prepare_upload(state.id, asset)
    uploaded = repository.mark_uploaded(prepared.id, "attachment-1")
    repository.apply_body(
        mapping.id,
        {
            "home": AppliedAttachment(
                asset.id,
                asset.sha256,
                uploaded.pending_content_id or "",
                "attachment-1",
            )
        },
    )

    restarted = EventAssetAttachmentsRepository(database_path)
    synchronized = restarted.list_for_mapping(mapping.id)[0]
    assert synchronized.status == "synced"
    assert synchronized.outlook_attachment_id == "attachment-1"
    assert synchronized.pending_asset_id is None

    restarted.reconcile_desired(mapping.id, {})
    removed = restarted.apply_body(mapping.id, {"home": None})[0]
    assert removed.status == "cleanup_pending"
    assert removed.obsolete_outlook_attachment_id == "attachment-1"
    cleaned = restarted.mark_cleanup_complete(removed.id)
    assert cleaned.status == "synced"
    assert cleaned.obsolete_outlook_attachment_id is None


def test_replacement_keeps_old_attachment_until_body_switch(tmp_path: Path) -> None:
    database_path = tmp_path / "sports.db"
    mapping = _setup(database_path)
    first = _approved_asset(database_path, digest="b" * 64, source="first")
    repository = EventAssetAttachmentsRepository(database_path)
    state = repository.reconcile_desired(mapping.id, {"home": first})[0]
    prepared = repository.prepare_upload(state.id, first)
    repository.mark_uploaded(state.id, "attachment-1")
    repository.apply_body(
        mapping.id,
        {
            "home": AppliedAttachment(
                first.id,
                first.sha256,
                prepared.pending_content_id or "",
                "attachment-1",
            )
        },
    )

    replacement = _approved_asset(
        database_path,
        digest="c" * 64,
        source="replacement",
    )
    changed = repository.reconcile_desired(mapping.id, {"home": replacement})[0]
    prepared_replacement = repository.prepare_upload(changed.id, replacement)
    repository.mark_uploaded(changed.id, "attachment-2")

    before_switch = repository.list_for_mapping(mapping.id)[0]
    assert before_switch.outlook_attachment_id == "attachment-1"
    assert before_switch.pending_outlook_attachment_id == "attachment-2"
    after_switch = repository.apply_body(
        mapping.id,
        {
            "home": AppliedAttachment(
                replacement.id,
                replacement.sha256,
                prepared_replacement.pending_content_id or "",
                "attachment-2",
            )
        },
    )[0]
    assert after_switch.outlook_attachment_id == "attachment-2"
    assert after_switch.obsolete_outlook_attachment_id == "attachment-1"


def test_asset_approval_and_disable_invalidate_affected_presentations(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "sports.db"
    mapping = _setup(database_path)
    asset = _approved_asset(database_path, digest="b" * 64, source="first")
    mappings = CalendarEventMappingsRepository(database_path)

    approved_revision = mappings.get_by_id(mapping.id)
    assert approved_revision is not None
    assert approved_revision.presentation_revision == mapping.presentation_revision + 1

    MediaAssetsRepository(database_path).disable(asset.asset_key)
    disabled_revision = mappings.get_by_id(mapping.id)
    assert disabled_revision is not None
    assert (
        disabled_revision.presentation_revision
        == approved_revision.presentation_revision + 1
    )
