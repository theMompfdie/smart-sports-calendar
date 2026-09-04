from dataclasses import dataclass
from enum import StrEnum


class MediaAssetError(ValueError):
    pass


class MediaOwnerType(StrEnum):
    PROJECT = "project"
    SPORT = "sport"
    COMPETITION = "competition"
    PARTICIPANT = "participant"


@dataclass(frozen=True)
class MediaAssetOwner:
    owner_type: MediaOwnerType
    project_key: str | None = None
    sport_id: int | None = None
    competition_id: int | None = None
    participant_id: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_type", MediaOwnerType(self.owner_type))
        actual = (
            self.project_key is not None,
            self.sport_id is not None,
            self.competition_id is not None,
            self.participant_id is not None,
        )
        expected = {
            MediaOwnerType.PROJECT: (True, False, False, False),
            MediaOwnerType.SPORT: (False, True, False, False),
            MediaOwnerType.COMPETITION: (False, False, True, False),
            MediaOwnerType.PARTICIPANT: (False, False, False, True),
        }[self.owner_type]
        if actual != expected:
            raise MediaAssetError(
                f"Invalid owner identifiers for {self.owner_type.value} media asset."
            )


@dataclass(frozen=True)
class MediaAssetWrite:
    asset_key: str
    owner: MediaAssetOwner
    variant: str
    mime_type: str
    width: int
    height: int
    byte_size: int
    sha256: str
    storage_path: str
    source_reference: str
    license_name: str | None = None
    permission_reference: str | None = None
    attribution: str | None = None
