"""Deterministic selection of approved media for one calendar event."""

import re

from app.database.media_assets_repository import MediaAsset, MediaAssetsRepository
from app.database.synchronization_query_repository import SynchronizationEvent
from app.domain.media_assets import MediaAssetOwner, MediaOwnerType

_FINAL_NAMES = frozenset(
    {
        "final",
        "finale",
        "finals",
        "grand_final",
        "championship",
        "championship_game",
        "super_bowl",
    }
)


class EventAssetSelector:
    """Resolve semantic slots without provider text or insertion-order fallback."""

    def __init__(self, repository: MediaAssetsRepository) -> None:
        self._repository = repository

    def select(self, event: SynchronizationEvent) -> dict[str, MediaAsset]:
        selected: dict[str, MediaAsset] = {}
        if event.competition is not None:
            competition = self._repository.get_active_for_owner_variant(
                MediaAssetOwner(
                    MediaOwnerType.COMPETITION,
                    competition_id=event.competition.id,
                ),
                "logo",
            )
            if competition is not None:
                selected["competition"] = competition

        for participant in event.participants:
            if participant.role not in {"home", "away"}:
                continue
            asset = self._repository.get_active_for_owner_variant(
                MediaAssetOwner(
                    MediaOwnerType.PARTICIPANT,
                    participant_id=participant.participant.id,
                ),
                "logo",
            )
            if asset is not None:
                selected[participant.role] = asset

        if self._is_final(event):
            project = MediaAssetOwner(
                MediaOwnerType.PROJECT,
                project_key="smart_sports_calendar",
            )
            final = self._repository.get_active_for_owner_variant(project, "final")
            if final is None:
                final = self._repository.get_active_for_owner_variant(
                    project,
                    "trophy",
                )
            if final is not None:
                selected["final"] = final
        return selected

    @classmethod
    def _is_final(cls, event: SynchronizationEvent) -> bool:
        return any(
            cls._normalize(value) in _FINAL_NAMES
            for value in (event.event.stage, event.event.round_name)
            if value is not None
        )

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
