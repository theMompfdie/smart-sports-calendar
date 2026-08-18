from dataclasses import dataclass
from datetime import UTC, datetime

from app.database.data_sources_repository import DataSourcesRepository
from app.database.fixture_import_repository import (
    FixtureImportConflictError,
    FixtureImportRecord,
    FixtureImportRepository,
    FixtureImportResult,
    FixtureImportScopeRecord,
    FixtureParticipantRecord,
)
from app.domain.competition_lifecycle import (
    CompetitionLifecycleScope,
    FixtureObservationScopeKind,
)
from app.providers.api_football.exceptions import (
    ProviderIntegrityError,
    ProviderResolutionError,
)
from app.providers.contracts import NormalizedFixture


@dataclass(frozen=True)
class FixtureImportScope:
    competition_id: int
    season_id: int
    observation_id: str
    observed_at_utc: datetime
    lifecycle: CompetitionLifecycleScope
    window_start_utc: datetime | None = None
    window_end_utc: datetime | None = None
    authoritative: bool = False
    filtered: bool = False

    def __post_init__(self) -> None:
        if self.competition_id <= 0 or self.season_id <= 0:
            raise ValueError("Fixture import scope IDs must be positive.")
        if not self.observation_id.strip():
            raise ValueError("Fixture import observation_id must not be blank.")
        self._require_utc(self.observed_at_utc, "observed_at_utc")
        if self.window_start_utc is not None:
            self._require_utc(self.window_start_utc, "window_start_utc")
        if self.window_end_utc is not None:
            self._require_utc(self.window_end_utc, "window_end_utc")
        if (
            self.window_start_utc is not None
            and self.window_end_utc is not None
            and self.window_start_utc > self.window_end_utc
        ):
            raise ValueError("Fixture import window start must not follow its end.")
        if self.filtered and self.lifecycle.complete:
            raise ValueError(
                "A filtered fixture observation cannot declare a complete scope."
            )
        if (
            self.lifecycle.scope_kind is FixtureObservationScopeKind.COMPLETE_SEASON
            and (self.window_start_utc is None or self.window_end_utc is None)
        ):
            raise ValueError(
                "A complete-season fixture observation requires a bounded UTC window."
            )

    @property
    def complete(self) -> bool:
        return self.lifecycle.complete

    @property
    def removal_eligible(self) -> bool:
        return (
            self.authoritative
            and not self.filtered
            and self.lifecycle.removal_reconciliation_supported
        )

    @staticmethod
    def _require_utc(value: datetime, field_name: str) -> None:
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise ValueError(f"{field_name} must be timezone-aware UTC.")


class ApiFootballFixtureImportService:
    def __init__(
        self,
        data_sources_repository: DataSourcesRepository,
        fixture_import_repository: FixtureImportRepository,
        source_key: str = "api_football",
    ) -> None:
        self._data_sources_repository = data_sources_repository
        self._fixture_import_repository = fixture_import_repository
        if not source_key.strip():
            raise ValueError("source_key must not be blank.")
        self._source_key = source_key.strip()

    def import_fixtures(
        self,
        fixtures: tuple[NormalizedFixture, ...],
        scope: FixtureImportScope,
    ) -> FixtureImportResult:
        self._validate_fixtures(fixtures, scope)
        source = self._data_sources_repository.get_by_key(self._source_key)
        if source is None:
            raise ProviderResolutionError(
                "Configured data source must exist before fixture import."
            )
        records = tuple(self._to_record(fixture) for fixture in fixtures)
        scope_record = FixtureImportScopeRecord(
            competition_id=scope.competition_id,
            season_id=scope.season_id,
            window_start_utc=scope.window_start_utc,
            window_end_utc=scope.window_end_utc,
            authoritative=scope.authoritative,
            lifecycle=scope.lifecycle,
            filtered=scope.filtered,
            observation_id=scope.observation_id.strip(),
            observed_at_utc=scope.observed_at_utc,
        )
        try:
            return self._fixture_import_repository.import_observation(
                source_id=source.id,
                fixtures=records,
                scope=scope_record,
            )
        except FixtureImportConflictError as error:
            raise ProviderIntegrityError(str(error)) from error

    @staticmethod
    def _validate_fixtures(
        fixtures: tuple[NormalizedFixture, ...],
        scope: FixtureImportScope,
    ) -> None:
        ApiFootballFixtureImportService._validate_complete_boundary(fixtures, scope)
        external_ids: set[str] = set()
        for fixture in fixtures:
            if not fixture.external_id.strip():
                raise ProviderIntegrityError("Fixture external ID must not be blank.")
            if fixture.external_id in external_ids:
                raise ProviderIntegrityError(
                    "Fixture observation contains a duplicate external ID: "
                    f"{fixture.external_id}."
                )
            external_ids.add(fixture.external_id)
            if (
                fixture.competition_id != scope.competition_id
                or fixture.season_id != scope.season_id
            ):
                raise ProviderIntegrityError(
                    "Fixture falls outside the declared import scope: "
                    f"external_id={fixture.external_id}."
                )
            if fixture.kickoff_confirmed and fixture.kickoff_utc is None:
                raise ProviderIntegrityError(
                    "Confirmed fixture kickoff must include a UTC datetime: "
                    f"external_id={fixture.external_id}."
                )
            if fixture.kickoff_utc is not None:
                FixtureImportScope._require_utc(
                    fixture.kickoff_utc,
                    f"fixture {fixture.external_id} kickoff_utc",
                )
                if (
                    scope.window_start_utc is not None
                    and fixture.kickoff_utc < scope.window_start_utc
                ) or (
                    scope.window_end_utc is not None
                    and fixture.kickoff_utc > scope.window_end_utc
                ):
                    raise ProviderIntegrityError(
                        "Fixture falls outside the declared UTC import window: "
                        f"external_id={fixture.external_id}."
                    )
            roles = [participant.role for participant in fixture.participants]
            if roles != ["home", "away"]:
                raise ProviderIntegrityError(
                    "Fixture must contain deterministic home and away participants: "
                    f"external_id={fixture.external_id}."
                )

    @staticmethod
    def _validate_complete_boundary(
        fixtures: tuple[NormalizedFixture, ...],
        scope: FixtureImportScope,
    ) -> None:
        lifecycle = scope.lifecycle
        if lifecycle.scope_kind not in {
            FixtureObservationScopeKind.COMPLETE_STAGE,
            FixtureObservationScopeKind.COMPLETE_ROUND,
        }:
            return
        if not fixtures:
            raise ProviderIntegrityError(
                "A complete stage or round observation must contain fixtures."
            )
        for fixture in fixtures:
            if (
                lifecycle.scope_kind is FixtureObservationScopeKind.COMPLETE_STAGE
                and fixture.stage != lifecycle.stage
            ):
                raise ProviderIntegrityError(
                    "Fixture falls outside the declared complete-stage scope: "
                    f"external_id={fixture.external_id}."
                )
            if lifecycle.scope_kind is FixtureObservationScopeKind.COMPLETE_ROUND and (
                fixture.round_name != lifecycle.round_name
                or (lifecycle.stage is not None and fixture.stage != lifecycle.stage)
            ):
                raise ProviderIntegrityError(
                    "Fixture falls outside the declared complete-round scope: "
                    f"external_id={fixture.external_id}."
                )

    def _to_record(self, fixture: NormalizedFixture) -> FixtureImportRecord:
        return FixtureImportRecord(
            external_id=fixture.external_id,
            sport_id=fixture.sport_id,
            competition_id=fixture.competition_id,
            season_id=fixture.season_id,
            event_type=fixture.event_type,
            title=fixture.title,
            participants=tuple(
                FixtureParticipantRecord(
                    participant_id=participant.participant_id,
                    role=participant.role,
                    position_number=participant.position_number,
                )
                for participant in fixture.participants
            ),
            kickoff_utc=fixture.kickoff_utc,
            kickoff_confirmed=fixture.kickoff_confirmed,
            timezone=fixture.timezone,
            status=fixture.status,
            stage=fixture.stage,
            round_name=fixture.round_name,
            sequence_number=fixture.sequence_number,
            venue_name=fixture.venue_name,
            city=fixture.city,
            source_updated_at=fixture.source_updated_at,
            metadata=fixture.metadata,
            event_key_prefix=self._source_key,
        )
