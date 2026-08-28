import re
from dataclasses import dataclass
from datetime import date

from app.providers.oefb_ical.exceptions import OefbIcalIntegrityError


@dataclass(frozen=True)
class OefbIcalCompetitionProfile:
    canonical_competition_key: str
    canonical_season_key: str
    competition_name: str
    provider_competition_id: int
    season_start_date: date
    season_end_date: date
    round_capacities: tuple[int, ...]


OEFB_CUP_PROFILE = OefbIcalCompetitionProfile(
    canonical_competition_key="oefb_cup",
    canonical_season_key="2026_27",
    competition_name="UNIQA ÖFB Cup",
    provider_competition_id=232362,
    season_start_date=date(2026, 7, 1),
    season_end_date=date(2027, 6, 30),
    round_capacities=(32, 16, 8, 4, 2, 1),
)

ROUND_PATTERN = re.compile(r"(?<!\d)([1-6])\.\s*Runde\b", re.IGNORECASE)


def resolve_round(description: str) -> tuple[str, int]:
    matches = {int(match) for match in ROUND_PATTERN.findall(description)}
    if len(matches) != 1:
        raise OefbIcalIntegrityError(
            "Provider event has a missing or contradictory round."
        )
    number = matches.pop()
    return f"round-{number}", number
