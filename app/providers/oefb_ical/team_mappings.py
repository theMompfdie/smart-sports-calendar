from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class OefbIcalTeamMapping:
    participant_key: str
    provider_name: str


OEFB_CUP_TEAM_MAPPINGS: Mapping[int, OefbIcalTeamMapping] = MappingProxyType({})


def resolve_team_key(
    provider_id: int,
    mappings: Mapping[int, OefbIcalTeamMapping] = OEFB_CUP_TEAM_MAPPINGS,
) -> str | None:
    mapping = mappings.get(provider_id)
    return None if mapping is None else mapping.participant_key
