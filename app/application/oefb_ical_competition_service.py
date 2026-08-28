"""Official ÖFB-Cup catalog mapping and permanent-partial normalization."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from app.config.settings import OefbIcalSettings
from app.database.competitions_repository import CompetitionsRepository
from app.database.data_sources_repository import DataSource, DataSourcesRepository
from app.database.participants_repository import Participant, ParticipantsRepository
from app.database.season_participants_repository import SeasonParticipantsRepository
from app.database.seasons_repository import SeasonsRepository
from app.database.source_mappings_repository import (
    SourceMappingConflictError,
    SourceMappingsRepository,
)
from app.database.sports_repository import SportsRepository
from app.domain.competition_lifecycle import CompetitionFormat
from app.providers.contracts import (
    NormalizedFixture,
    NormalizedFixtureBatch,
    NormalizedFixtureParticipant,
    RateLimitSnapshot,
)
from app.providers.oefb_ical.adapter import OefbIcalSnapshotAdapter
from app.providers.oefb_ical.exceptions import (
    OefbIcalIntegrityError,
    OefbIcalResolutionError,
)
from app.providers.oefb_ical.models import OefbIcalEvent
from app.providers.oefb_ical.profiles import OEFB_CUP_PROFILE, resolve_round
from app.providers.oefb_ical.team_mappings import (
    OEFB_CUP_TEAM_MAPPINGS,
    OefbIcalTeamMapping,
)

OEFB_ICAL_SOURCE_KEY = "oefb_ical"
OEFB_ICAL_PUBLIC_BASE_URL = "https://www.fussballoesterreich.at"
OEFB_ICAL_ATTRIBUTION = (
    "Fixture data provided by the Austrian Football Association (ÖFB): "
    "https://www.oefb.at/cup"
)
EXPECTED_PARTICIPANT_COUNT = 64


def register_oefb_ical_source(
    settings: OefbIcalSettings,
    repository: DataSourcesRepository,
) -> DataSource:
    return repository.upsert(
        source_key=OEFB_ICAL_SOURCE_KEY,
        name="Official ÖFB iCalendar",
        base_url=OEFB_ICAL_PUBLIC_BASE_URL,
        is_active=settings.enabled,
        metadata={
            "authentication": "opaque_operator_subscription",
            "attribution": OEFB_ICAL_ATTRIBUTION,
            "authority_scope": "partial",
            "license": "private-non-commercial-use",
            "provider": "Austrian Football Association (ÖFB)",
        },
    )


@dataclass(frozen=True)
class _CanonicalContext:
    sport_id: int
    competition_id: int
    season_id: int
    season_start_date: date
    season_end_date: date
    participants_by_provider_id: dict[int, Participant]


class OefbIcalCompetitionService:
    def __init__(
        self,
        settings: OefbIcalSettings,
        adapter: OefbIcalSnapshotAdapter,
        sports_repository: SportsRepository,
        competitions_repository: CompetitionsRepository,
        seasons_repository: SeasonsRepository,
        participants_repository: ParticipantsRepository,
        season_participants_repository: SeasonParticipantsRepository,
        data_sources_repository: DataSourcesRepository,
        source_mappings_repository: SourceMappingsRepository,
        team_mappings: Mapping[int, OefbIcalTeamMapping] = OEFB_CUP_TEAM_MAPPINGS,
    ) -> None:
        self._settings = settings
        self._adapter = adapter
        self._sports_repository = sports_repository
        self._competitions_repository = competitions_repository
        self._seasons_repository = seasons_repository
        self._participants_repository = participants_repository
        self._season_participants_repository = season_participants_repository
        self._data_sources_repository = data_sources_repository
        self._source_mappings_repository = source_mappings_repository
        self._team_mappings = team_mappings

    def fetch_normalized_snapshot(self) -> NormalizedFixtureBatch:
        snapshot = self._adapter.fetch_snapshot()
        context = self._map_catalog()
        current_events = tuple(
            event
            for event in snapshot.events
            if context.season_start_date
            <= event.kickoff_utc.date()
            <= context.season_end_date
        )
        if not current_events:
            raise OefbIcalIntegrityError(
                "Provider returned no fixtures in the canonical season window."
            )
        self._validate_uid_growth(current_events)
        return NormalizedFixtureBatch(
            fixtures=tuple(
                self._normalize_event(event, context) for event in current_events
            ),
            competition_id=context.competition_id,
            competition_format=CompetitionFormat.KNOCKOUT_CUP,
            season_id=context.season_id,
            season_start_date=context.season_start_date,
            season_end_date=context.season_end_date,
            fetched_at_utc=snapshot.fetched_at_utc,
            page_count=1,
            request_attempts=snapshot.request_attempts,
            rate_limits=RateLimitSnapshot(None, None, None, None, None),
        )

    def _map_catalog(self) -> _CanonicalContext:
        if len(self._team_mappings) != EXPECTED_PARTICIPANT_COUNT:
            raise OefbIcalResolutionError(
                "Reviewed ÖFB-Cup mapping must contain exactly 64 participants."
            )
        football = self._sports_repository.get_by_key("football")
        if football is None:
            raise OefbIcalResolutionError("Canonical football sport is missing.")
        competition = self._competitions_repository.get_by_key(
            sport_id=football.id,
            competition_key=OEFB_CUP_PROFILE.canonical_competition_key,
        )
        if competition is None:
            raise OefbIcalResolutionError("Canonical competition is missing.")
        if competition.competition_type is not CompetitionFormat.KNOCKOUT_CUP:
            raise OefbIcalResolutionError("Canonical competition format is invalid.")
        season = self._seasons_repository.get_by_key(
            competition_id=competition.id,
            season_key=OEFB_CUP_PROFILE.canonical_season_key,
        )
        if season is None or not season.is_current:
            raise OefbIcalResolutionError("Canonical current season is missing.")
        if (season.start_date, season.end_date) != (
            OEFB_CUP_PROFILE.season_start_date.isoformat(),
            OEFB_CUP_PROFILE.season_end_date.isoformat(),
        ):
            raise OefbIcalResolutionError("Canonical season dates are invalid.")
        source = register_oefb_ical_source(
            self._settings, self._data_sources_repository
        )
        self._upsert_mapping(
            source.id,
            "competition",
            competition.id,
            str(OEFB_CUP_PROFILE.provider_competition_id),
            {"provider_name": OEFB_CUP_PROFILE.competition_name},
        )
        self._upsert_mapping(
            source.id,
            "season",
            season.id,
            (
                f"{OEFB_CUP_PROFILE.provider_competition_id}:"
                f"{OEFB_CUP_PROFILE.canonical_season_key}"
            ),
            {"season_key": OEFB_CUP_PROFILE.canonical_season_key},
        )
        participants_by_provider_id: dict[int, Participant] = {}
        resolved_participant_ids: set[int] = set()
        for provider_id, mapping in self._team_mappings.items():
            participant = self._participants_repository.get_by_key(
                sport_id=football.id,
                participant_key=mapping.participant_key,
            )
            if participant is None or participant.id in resolved_participant_ids:
                raise OefbIcalResolutionError(
                    "Reviewed ÖFB mapping references an invalid canonical participant."
                )
            participants_by_provider_id[provider_id] = participant
            resolved_participant_ids.add(participant.id)
            self._upsert_mapping(
                source.id,
                "participant",
                participant.id,
                str(provider_id),
                {"provider_name": mapping.provider_name},
            )
            self._season_participants_repository.upsert(
                season_id=season.id,
                participant_id=participant.id,
            )
        return _CanonicalContext(
            sport_id=football.id,
            competition_id=competition.id,
            season_id=season.id,
            season_start_date=OEFB_CUP_PROFILE.season_start_date,
            season_end_date=OEFB_CUP_PROFILE.season_end_date,
            participants_by_provider_id=participants_by_provider_id,
        )

    def _validate_uid_growth(self, events: tuple[OefbIcalEvent, ...]) -> None:
        source = self._data_sources_repository.get_by_key(OEFB_ICAL_SOURCE_KEY)
        if source is None:
            raise OefbIcalResolutionError("Active ÖFB source is missing.")
        persisted_uids = {
            mapping.external_id
            for mapping in self._source_mappings_repository.get_for_source(
                source.id, "event"
            )
        }
        observed_uids = {event.uid for event in events}
        if not persisted_uids.issubset(observed_uids):
            raise OefbIcalIntegrityError(
                "Provider current-season UID set shrank or replaced identities."
            )

    @staticmethod
    def _normalize_event(
        event: OefbIcalEvent,
        context: _CanonicalContext,
    ) -> NormalizedFixture:
        try:
            home = context.participants_by_provider_id[event.home_provider_id]
            away = context.participants_by_provider_id[event.away_provider_id]
        except KeyError as error:
            raise OefbIcalIntegrityError(
                "Provider event references an unknown participant."
            ) from error
        round_name, sequence_number = resolve_round(event.description)
        return NormalizedFixture(
            external_id=event.uid,
            sport_id=context.sport_id,
            competition_id=context.competition_id,
            season_id=context.season_id,
            event_type="match",
            title=f"{home.name} vs {away.name}",
            participants=(
                NormalizedFixtureParticipant(home.id, "home", 1),
                NormalizedFixtureParticipant(away.id, "away", 2),
            ),
            kickoff_utc=event.kickoff_utc,
            kickoff_confirmed=True,
            timezone="UTC",
            status="scheduled",
            stage="knockout",
            round_name=round_name,
            sequence_number=sequence_number,
            venue_name=event.location,
            city=None,
            source_updated_at=event.dtstamp_utc,
            metadata={"official_url": event.url},
        )

    def _upsert_mapping(
        self,
        source_id: int,
        object_type: str,
        internal_id: int,
        external_id: str,
        metadata: dict[str, object],
    ) -> None:
        external = self._source_mappings_repository.get_by_external_id(
            source_id=source_id,
            object_type=object_type,
            external_id=external_id,
        )
        internal = self._source_mappings_repository.get_by_internal_id(
            source_id=source_id,
            object_type=object_type,
            internal_id=internal_id,
        )
        if (external is not None and external.internal_id != internal_id) or (
            internal is not None and internal.external_id != external_id
        ):
            raise OefbIcalIntegrityError(
                "ÖFB iCalendar mapping conflicts with a persisted identity."
            )
        try:
            self._source_mappings_repository.upsert(
                source_id=source_id,
                object_type=object_type,
                internal_id=internal_id,
                external_id=external_id,
                metadata=metadata,
            )
        except SourceMappingConflictError as error:
            raise OefbIcalIntegrityError(
                "ÖFB iCalendar mapping conflicted during persistence."
            ) from error
