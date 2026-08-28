import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass

from app.config.settings import load_oefb_ical_settings
from app.providers.api_football.exceptions import ProviderConfigurationError
from app.providers.oefb_ical.adapter import OefbIcalCompetitionAdapter
from app.providers.oefb_ical.client import OefbIcalClient
from app.providers.oefb_ical.exceptions import OefbIcalError
from app.providers.oefb_ical.models import OefbIcalSnapshot
from app.providers.oefb_ical.profiles import OEFB_CUP_PROFILE

EXPECTED_PARTICIPANT_COUNT = 64
SUMMARY_SEPARATOR = " : "


class OefbIcalCatalogCandidateError(RuntimeError):
    """A secret-safe failure while deriving reviewed catalog candidates."""


@dataclass(frozen=True)
class OefbIcalParticipantCandidate:
    provider_id: int
    provider_name: str


@dataclass(frozen=True)
class OefbIcalCatalogCandidateEvidence:
    competition_key: str
    provider_competition_id: int
    season_key: str
    season_start_date: str
    season_end_date: str
    observed_at_utc: str
    current_event_count: int
    participant_count: int
    participants: tuple[OefbIcalParticipantCandidate, ...]


def observe_oefb_ical_catalog(
    snapshot: OefbIcalSnapshot,
) -> OefbIcalCatalogCandidateEvidence:
    current_events = tuple(
        event
        for event in snapshot.events
        if OEFB_CUP_PROFILE.season_start_date
        <= event.kickoff_utc.date()
        <= OEFB_CUP_PROFILE.season_end_date
    )
    if not current_events:
        raise OefbIcalCatalogCandidateError(
            "Provider returned no fixtures in the approved season window."
        )
    names_by_id: dict[int, str] = {}
    ids_by_normalized_name: dict[str, int] = {}
    for event in current_events:
        home_name, away_name = _participant_names(event.summary)
        _record_participant(
            names_by_id,
            ids_by_normalized_name,
            event.home_provider_id,
            home_name,
        )
        _record_participant(
            names_by_id,
            ids_by_normalized_name,
            event.away_provider_id,
            away_name,
        )
    if len(names_by_id) != EXPECTED_PARTICIPANT_COUNT:
        raise OefbIcalCatalogCandidateError(
            "Expected exactly 64 distinct current-season participants."
        )
    participants = tuple(
        OefbIcalParticipantCandidate(provider_id, provider_name)
        for provider_id, provider_name in sorted(names_by_id.items())
    )
    return OefbIcalCatalogCandidateEvidence(
        competition_key=OEFB_CUP_PROFILE.canonical_competition_key,
        provider_competition_id=OEFB_CUP_PROFILE.provider_competition_id,
        season_key=OEFB_CUP_PROFILE.canonical_season_key,
        season_start_date=OEFB_CUP_PROFILE.season_start_date.isoformat(),
        season_end_date=OEFB_CUP_PROFILE.season_end_date.isoformat(),
        observed_at_utc=snapshot.fetched_at_utc.isoformat(),
        current_event_count=len(current_events),
        participant_count=len(participants),
        participants=participants,
    )


def render_catalog_candidates(evidence: OefbIcalCatalogCandidateEvidence) -> str:
    return json.dumps(asdict(evidence), ensure_ascii=False, indent=2, sort_keys=True)


def _participant_names(summary: str) -> tuple[str, str]:
    parts = summary.split(SUMMARY_SEPARATOR)
    if len(parts) != 2 or any(not part.strip() for part in parts):
        raise OefbIcalCatalogCandidateError(
            "Provider summary does not contain one unambiguous participant pair."
        )
    return parts[0].strip(), parts[1].strip()


def _record_participant(
    names_by_id: dict[int, str],
    ids_by_normalized_name: dict[str, int],
    provider_id: int,
    provider_name: str,
) -> None:
    previous_name = names_by_id.get(provider_id)
    if previous_name is not None and previous_name != provider_name:
        raise OefbIcalCatalogCandidateError(
            "Provider participant ID has inconsistent names."
        )
    normalized_name = provider_name.casefold()
    previous_id = ids_by_normalized_name.get(normalized_name)
    if previous_id is not None and previous_id != provider_id:
        raise OefbIcalCatalogCandidateError(
            "Provider participant name has inconsistent identities."
        )
    names_by_id[provider_id] = provider_name
    ids_by_normalized_name[normalized_name] = provider_id


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read the operator-configured official ÖFB iCalendar feed and print "
            "only secret-safe 2026/27 participant mapping candidates."
        )
    )
    parser.parse_args(argv)
    try:
        settings = load_oefb_ical_settings()
        snapshot = OefbIcalCompetitionAdapter(OefbIcalClient(settings)).fetch_snapshot()
        evidence = observe_oefb_ical_catalog(snapshot)
    except (
        OefbIcalCatalogCandidateError,
        OefbIcalError,
        ProviderConfigurationError,
    ) as error:
        parser.exit(status=1, message=f"ÖFB catalog observation failed: {error}\n")
    print(render_catalog_candidates(evidence))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
