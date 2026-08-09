from dataclasses import dataclass
from datetime import date

from app.database.competitions_repository import CompetitionsRepository
from app.database.data_sources_repository import DataSourcesRepository
from app.database.participants_repository import ParticipantsRepository
from app.database.seasons_repository import SeasonsRepository
from app.database.source_mappings_repository import SourceMappingsRepository
from app.database.sports_repository import SportsRepository
from app.providers.api_football.catalog_adapter import PREMIER_LEAGUE_ID
from app.providers.api_football.exceptions import ProviderResolutionError
from app.providers.api_football.fixture_adapter import ApiFootballFixtureAdapter
from app.providers.api_football.fixture_models import (
    ApiFootballFixture,
    ProviderFixtureStatus,
)
from app.providers.contracts import (
    NormalizedFixture,
    NormalizedFixtureBatch,
    NormalizedFixtureParticipant,
)


class ApiFootballFixtureNormalizationService:
    def __init__(
        self,
        adapter: ApiFootballFixtureAdapter,
        sports_repository: SportsRepository,
        competitions_repository: CompetitionsRepository,
        seasons_repository: SeasonsRepository,
        participants_repository: ParticipantsRepository,
        data_sources_repository: DataSourcesRepository,
        source_mappings_repository: SourceMappingsRepository,
    ) -> None:
        self._adapter = adapter
        self._sports_repository = sports_repository
        self._competitions_repository = competitions_repository
        self._seasons_repository = seasons_repository
        self._participants_repository = participants_repository
        self._data_sources_repository = data_sources_repository
        self._source_mappings_repository = source_mappings_repository

    def normalize_current_premier_league(self) -> tuple[NormalizedFixture, ...]:
        return self.normalize_current_premier_league_batch().fixtures

    def normalize_current_premier_league_batch(self) -> NormalizedFixtureBatch:
        context = self._resolve_context()
        batch = self._adapter.fetch_premier_league_fixture_batch(
            season_year=context.season_year
        )
        return NormalizedFixtureBatch(
            fixtures=tuple(
                self._normalize(fixture, context) for fixture in batch.fixtures
            ),
            competition_id=context.competition_id,
            season_id=context.season_id,
            season_start_date=context.season_start_date,
            season_end_date=context.season_end_date,
            fetched_at_utc=batch.fetched_at_utc,
            page_count=batch.page_count,
            request_attempts=batch.request_attempts,
            rate_limits=batch.rate_limits,
        )

    def _resolve_context(self) -> "_NormalizationContext":
        source = self._data_sources_repository.get_by_key("api_football")
        if source is None:
            raise ProviderResolutionError(
                "API-Football data source must exist before fixture normalization."
            )
        football = self._sports_repository.get_by_key("football")
        if football is None:
            raise ProviderResolutionError(
                "Canonical football sport must exist before fixture normalization."
            )
        competition = self._competitions_repository.get_by_key(
            sport_id=football.id,
            competition_key="premier_league",
        )
        if competition is None:
            raise ProviderResolutionError(
                "Canonical Premier League must exist before fixture normalization."
            )
        seasons = self._seasons_repository.get_current_for_competition(competition.id)
        if len(seasons) != 1:
            raise ProviderResolutionError(
                "Canonical Premier League must have exactly one fully dated current "
                "season."
            )
        season = seasons[0]
        start_date = season.start_date
        end_date = season.end_date
        if start_date is None or end_date is None:
            raise ProviderResolutionError(
                "Canonical Premier League must have exactly one fully dated current "
                "season."
            )
        try:
            season_start_date = date.fromisoformat(start_date)
            season_end_date = date.fromisoformat(end_date)
        except ValueError as error:
            raise ProviderResolutionError(
                "Canonical current Premier League season has an invalid start date."
            ) from error
        if season_end_date < season_start_date:
            raise ProviderResolutionError(
                "Canonical current Premier League season has an invalid date range."
            )
        season_year = season_start_date.year

        self._require_mapping(
            source_id=source.id,
            object_type="competition",
            external_id=str(PREMIER_LEAGUE_ID),
            internal_id=competition.id,
        )
        self._require_mapping(
            source_id=source.id,
            object_type="season",
            external_id=str(season_year),
            internal_id=season.id,
        )
        return _NormalizationContext(
            source_id=source.id,
            sport_id=football.id,
            competition_id=competition.id,
            season_id=season.id,
            season_year=season_year,
            season_start_date=season_start_date,
            season_end_date=season_end_date,
        )

    def _normalize(
        self,
        fixture: ApiFootballFixture,
        context: "_NormalizationContext",
    ) -> NormalizedFixture:
        normalized_participants: list[NormalizedFixtureParticipant] = []
        participant_names: list[str] = []
        for position, provider_participant in enumerate(
            fixture.participants,
            start=1,
        ):
            mapping = self._source_mappings_repository.get_by_external_id(
                source_id=context.source_id,
                object_type="participant",
                external_id=provider_participant.external_id,
            )
            if mapping is None:
                raise ProviderResolutionError(
                    "API-Football fixture team has no canonical source mapping: "
                    f"external_id={provider_participant.external_id}."
                )
            participant = self._participants_repository.get_by_id(mapping.internal_id)
            if (
                participant is None
                or participant.sport_id != context.sport_id
                or participant.participant_type != "team"
            ):
                raise ProviderResolutionError(
                    "API-Football fixture team mapping does not resolve to a "
                    f"canonical football participant: external_id="
                    f"{provider_participant.external_id}."
                )
            normalized_participants.append(
                NormalizedFixtureParticipant(
                    participant_id=participant.id,
                    role=provider_participant.role,
                    position_number=position,
                )
            )
            participant_names.append(participant.name)

        metadata = None
        if fixture.status is ProviderFixtureStatus.NOT_PLAYED:
            metadata = {
                "provider_status_code": fixture.provider_status_code,
                "provider_status_reason": fixture.provider_status_reason,
            }

        return NormalizedFixture(
            external_id=fixture.external_id,
            sport_id=context.sport_id,
            competition_id=context.competition_id,
            season_id=context.season_id,
            event_type="match",
            title=f"{participant_names[0]} vs {participant_names[1]}",
            participants=tuple(normalized_participants),
            kickoff_utc=fixture.kickoff_utc,
            kickoff_confirmed=fixture.kickoff_confirmed,
            timezone="UTC",
            status=(
                "cancelled"
                if fixture.status is ProviderFixtureStatus.NOT_PLAYED
                else fixture.status.value
            ),
            stage=fixture.stage,
            round_name=fixture.round_name,
            sequence_number=fixture.sequence_number,
            venue_name=fixture.venue_name,
            city=fixture.venue_city,
            source_updated_at=fixture.source_updated_at,
            metadata=metadata,
        )

    def _require_mapping(
        self,
        source_id: int,
        object_type: str,
        external_id: str,
        internal_id: int,
    ) -> None:
        mapping = self._source_mappings_repository.get_by_external_id(
            source_id=source_id,
            object_type=object_type,
            external_id=external_id,
        )
        if mapping is None or mapping.internal_id != internal_id:
            raise ProviderResolutionError(
                "API-Football fixture scope mapping is missing or conflicting: "
                f"object_type={object_type}, external_id={external_id}."
            )


@dataclass(frozen=True)
class _NormalizationContext:
    source_id: int
    sport_id: int
    competition_id: int
    season_id: int
    season_year: int
    season_start_date: date
    season_end_date: date
