"""Competition-neutral OpenLigaDB catalog mapping and normalization."""

from dataclasses import dataclass
from datetime import date

from app.config.settings import OpenLigaDBSettings
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
from app.providers.openligadb.adapter import OpenLigaDBSnapshotAdapter
from app.providers.openligadb.exceptions import (
    OpenLigaDBIntegrityError,
    OpenLigaDBResolutionError,
)
from app.providers.openligadb.models import OpenLigaDBMatch, OpenLigaDBSnapshot
from app.providers.openligadb.profiles import (
    DFB_POKAL_PROFILE,
    OpenLigaDBCompetitionProfile,
)
from app.providers.openligadb.team_mappings import (
    get_reviewed_team_keys,
    resolve_team_key,
)

OPENLIGADB_SOURCE_KEY = "openligadb"
OPENLIGADB_ATTRIBUTION = (
    "Fixture data provided by OpenLigaDB (ODbL 1.0): https://www.openligadb.de/"
)


def register_openligadb_source(
    settings: OpenLigaDBSettings,
    repository: DataSourcesRepository,
) -> DataSource:
    return repository.upsert(
        source_key=OPENLIGADB_SOURCE_KEY,
        name="OpenLigaDB",
        base_url=settings.base_url,
        is_active=settings.enabled,
        metadata={
            "api_version_family": "v1",
            "authentication": "none",
            "attribution": OPENLIGADB_ATTRIBUTION,
            "license": "ODbL-1.0",
            "provider": "OpenLigaDB",
        },
    )


@dataclass(frozen=True)
class _CanonicalContext:
    sport_id: int
    competition_id: int
    competition_format: CompetitionFormat
    season_id: int
    season_start_date: date
    season_end_date: date
    participants_by_provider_id: dict[int, Participant]


class OpenLigaDBCompetitionService:
    def __init__(
        self,
        settings: OpenLigaDBSettings,
        adapter: OpenLigaDBSnapshotAdapter,
        sports_repository: SportsRepository,
        competitions_repository: CompetitionsRepository,
        seasons_repository: SeasonsRepository,
        participants_repository: ParticipantsRepository,
        season_participants_repository: SeasonParticipantsRepository,
        data_sources_repository: DataSourcesRepository,
        source_mappings_repository: SourceMappingsRepository,
        profile: OpenLigaDBCompetitionProfile = DFB_POKAL_PROFILE,
    ) -> None:
        if adapter.profile != profile:
            raise ValueError("OpenLigaDB adapter and service profiles differ.")
        self._settings = settings
        self._adapter = adapter
        self.profile = profile
        self._sports_repository = sports_repository
        self._competitions_repository = competitions_repository
        self._seasons_repository = seasons_repository
        self._participants_repository = participants_repository
        self._season_participants_repository = season_participants_repository
        self._data_sources_repository = data_sources_repository
        self._source_mappings_repository = source_mappings_repository

    def fetch_normalized_snapshot(self) -> NormalizedFixtureBatch:
        snapshot = self._adapter.fetch_snapshot()
        context = self._map_catalog(snapshot)
        return NormalizedFixtureBatch(
            fixtures=tuple(
                self._normalize_match(match, context) for match in snapshot.matches
            ),
            competition_id=context.competition_id,
            competition_format=context.competition_format,
            season_id=context.season_id,
            season_start_date=context.season_start_date,
            season_end_date=context.season_end_date,
            fetched_at_utc=snapshot.fetched_at_utc,
            page_count=1,
            request_attempts=snapshot.request_attempts,
            rate_limits=RateLimitSnapshot(None, None, None, None, None),
        )

    def _map_catalog(self, snapshot: OpenLigaDBSnapshot) -> _CanonicalContext:
        football = self._sports_repository.get_by_key("football")
        if football is None:
            raise OpenLigaDBResolutionError("Canonical football sport is missing.")
        competition = self._competitions_repository.get_by_key(
            sport_id=football.id,
            competition_key=self.profile.canonical_competition_key,
        )
        if competition is None:
            raise OpenLigaDBResolutionError("Canonical competition is missing.")
        expected_format = self.profile.competition_format
        if competition.competition_type is not expected_format:
            raise OpenLigaDBResolutionError("Canonical competition format is invalid.")
        seasons = self._seasons_repository.get_current_for_competition(competition.id)
        if len(seasons) != 1:
            raise OpenLigaDBResolutionError(
                "Canonical competition must have exactly one current season."
            )
        season = seasons[0]
        if season.season_key != self.profile.canonical_season_key:
            raise OpenLigaDBResolutionError(
                "Canonical current season does not match the profile."
            )
        if season.start_date is None or season.end_date is None:
            raise OpenLigaDBResolutionError("Canonical season dates are incomplete.")
        try:
            start_date = date.fromisoformat(season.start_date)
            end_date = date.fromisoformat(season.end_date)
        except ValueError as error:
            raise OpenLigaDBResolutionError(
                "Canonical season dates are invalid."
            ) from error
        if (start_date, end_date) != (
            snapshot.season_start_date,
            snapshot.season_end_date,
        ):
            raise OpenLigaDBIntegrityError(
                "Provider and canonical season dates differ."
            )

        participants_by_provider_id: dict[int, Participant] = {}
        resolved_team_keys: set[str] = set()
        for team in snapshot.teams:
            participant_key = resolve_team_key(
                self.profile.canonical_competition_key, team.id, team.name
            )
            if participant_key is None:
                raise OpenLigaDBIntegrityError(
                    "Provider team identity does not match the reviewed mapping: "
                    f"competition={self.profile.canonical_competition_key} "
                    f"provider_team_id={team.id}."
                )
            participant = self._participants_repository.get_by_key(
                sport_id=football.id, participant_key=participant_key
            )
            if participant is None:
                raise OpenLigaDBResolutionError(
                    "Reviewed provider mapping references an unknown participant."
                )
            participants_by_provider_id[team.id] = participant
            resolved_team_keys.add(participant_key)
        reviewed_team_keys = get_reviewed_team_keys(
            self.profile.canonical_competition_key
        )
        if not resolved_team_keys.issubset(reviewed_team_keys):
            raise OpenLigaDBIntegrityError(
                "Provider participant collection exceeds the reviewed set."
            )
        if self.profile.expected_participant_count is not None and (
            len(resolved_team_keys) != self.profile.expected_participant_count
            or resolved_team_keys != reviewed_team_keys
        ):
            raise OpenLigaDBIntegrityError(
                "Provider participant collection differs from the reviewed set."
            )

        source = register_openligadb_source(
            self._settings, self._data_sources_repository
        )
        self._upsert_mapping(
            source.id,
            "competition",
            competition.id,
            str(snapshot.league_id),
            {"provider_shortcut": snapshot.league_shortcut},
        )
        self._upsert_mapping(
            source.id,
            "season",
            season.id,
            f"{snapshot.league_id}:{snapshot.league_season}",
            {"league_season": snapshot.league_season},
        )
        for team in snapshot.teams:
            participant = participants_by_provider_id[team.id]
            self._upsert_mapping(
                source.id,
                "participant",
                participant.id,
                team.external_id,
                {
                    "provider_name": team.name,
                    "provider_short_name": team.short_name,
                },
            )
            self._season_participants_repository.upsert(
                season_id=season.id, participant_id=participant.id
            )
        return _CanonicalContext(
            sport_id=football.id,
            competition_id=competition.id,
            competition_format=competition.competition_type,
            season_id=season.id,
            season_start_date=start_date,
            season_end_date=end_date,
            participants_by_provider_id=participants_by_provider_id,
        )

    def _normalize_match(
        self, match: OpenLigaDBMatch, context: _CanonicalContext
    ) -> NormalizedFixture:
        home = context.participants_by_provider_id[match.home_team_id]
        away = context.participants_by_provider_id[match.away_team_id]
        return NormalizedFixture(
            external_id=match.external_id,
            sport_id=context.sport_id,
            competition_id=context.competition_id,
            season_id=context.season_id,
            event_type="match",
            title=f"{home.name} vs {away.name}",
            participants=(
                NormalizedFixtureParticipant(home.id, "home", 1),
                NormalizedFixtureParticipant(away.id, "away", 2),
            ),
            kickoff_utc=match.kickoff_utc,
            kickoff_confirmed=True,
            timezone="UTC",
            status=match.status,
            stage=self.profile.normalized_stage,
            round_name=match.round_name,
            sequence_number=match.group_order_id,
            venue_name=None,
            city=None,
            source_updated_at=match.source_updated_at,
            metadata={
                "provider_group_id": str(match.group_id),
                "provider_group_order_id": str(match.group_order_id),
            },
            stage_kind=self.profile.stage_kind,
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
            source_id=source_id, object_type=object_type, external_id=external_id
        )
        internal = self._source_mappings_repository.get_by_internal_id(
            source_id=source_id, object_type=object_type, internal_id=internal_id
        )
        if (external is not None and external.internal_id != internal_id) or (
            internal is not None and internal.external_id != external_id
        ):
            raise OpenLigaDBIntegrityError(
                "OpenLigaDB mapping conflicts with an existing source mapping."
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
            raise OpenLigaDBIntegrityError(
                "OpenLigaDB mapping conflicted during persistence."
            ) from error


OpenLigaDBDFBPokalService = OpenLigaDBCompetitionService
