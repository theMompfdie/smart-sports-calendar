from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from app.config.settings import ApiFootballSettings
from app.database.competitions_repository import Competition, CompetitionsRepository
from app.database.data_sources_repository import DataSource, DataSourcesRepository
from app.database.participants_repository import Participant, ParticipantsRepository
from app.database.season_participants_repository import SeasonParticipantsRepository
from app.database.seasons_repository import Season, SeasonsRepository
from app.database.source_mappings_repository import (
    SourceMapping,
    SourceMappingConflictError,
    SourceMappingsRepository,
)
from app.database.sports_repository import SportsRepository
from app.providers.api_football.catalog_adapter import ApiFootballCatalogAdapter
from app.providers.api_football.catalog_models import (
    ApiFootballLeague,
    ApiFootballSeason,
    ApiFootballTeam,
)
from app.providers.api_football.exceptions import (
    ProviderIntegrityError,
    ProviderResolutionError,
)

API_FOOTBALL_SOURCE_KEY = "api_football"


def register_api_football_source(
    settings: ApiFootballSettings,
    repository: DataSourcesRepository,
) -> DataSource:
    return repository.upsert(
        source_key=API_FOOTBALL_SOURCE_KEY,
        name="API-Football",
        base_url=settings.base_url,
        is_active=settings.enabled,
        metadata={
            "api_version_family": "v3",
            "authentication": "x-apisports-key",
            "provider": "API-Football",
        },
    )


@dataclass(frozen=True)
class ApiFootballCatalogMappingResult:
    data_source: DataSource
    competition: Competition
    season: Season
    mappings: tuple[SourceMapping, ...]
    participants: tuple[Participant, ...]


class ApiFootballCatalogService:
    def __init__(
        self,
        settings: ApiFootballSettings,
        adapter: ApiFootballCatalogAdapter,
        sports_repository: SportsRepository,
        competitions_repository: CompetitionsRepository,
        seasons_repository: SeasonsRepository,
        participants_repository: ParticipantsRepository,
        season_participants_repository: SeasonParticipantsRepository,
        data_sources_repository: DataSourcesRepository,
        source_mappings_repository: SourceMappingsRepository,
        team_mapping: Mapping[str, str],
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
        self._team_mapping = dict(team_mapping)

    def map_current_premier_league(self) -> ApiFootballCatalogMappingResult:
        league = self._adapter.find_premier_league()
        provider_season = self._adapter.find_current_season(league)
        teams = self._adapter.fetch_teams(
            league_id=league.id,
            season_year=provider_season.year,
        )

        competition, season, participants = self._resolve_canonical_catalog(
            provider_season=provider_season,
            teams=teams,
        )
        data_source = self._register_data_source()
        planned_mappings = self._planned_mappings(
            league=league,
            provider_season=provider_season,
            teams=teams,
            competition=competition,
            season=season,
            participants=participants,
        )
        self._validate_mapping_conflicts(
            source_id=data_source.id,
            planned_mappings=planned_mappings,
        )

        mappings = tuple(
            self._upsert_mapping(
                source_id=data_source.id,
                object_type=object_type,
                internal_id=internal_id,
                external_id=external_id,
                metadata=metadata,
            )
            for object_type, internal_id, external_id, metadata in planned_mappings
        )

        for participant in participants:
            if (
                self._season_participants_repository.get(
                    season_id=season.id,
                    participant_id=participant.id,
                )
                is None
            ):
                self._season_participants_repository.upsert(
                    season_id=season.id,
                    participant_id=participant.id,
                )

        return ApiFootballCatalogMappingResult(
            data_source=data_source,
            competition=competition,
            season=season,
            mappings=mappings,
            participants=participants,
        )

    def _resolve_canonical_catalog(
        self,
        provider_season: ApiFootballSeason,
        teams: tuple[ApiFootballTeam, ...],
    ) -> tuple[Competition, Season, tuple[Participant, ...]]:
        football = self._sports_repository.get_by_key("football")
        if football is None:
            raise ProviderResolutionError(
                "Canonical football sport must exist before provider mapping."
            )

        competition = self._competitions_repository.get_by_key(
            sport_id=football.id,
            competition_key="premier_league",
        )
        if competition is None:
            raise ProviderResolutionError(
                "Canonical Premier League competition must exist before mapping."
            )

        current_seasons = self._seasons_repository.get_current_for_competition(
            competition.id
        )
        if len(current_seasons) != 1:
            raise ProviderResolutionError(
                "Canonical Premier League must have exactly one current season; "
                f"received {len(current_seasons)}."
            )
        season = current_seasons[0]
        if season.start_date is None:
            raise ProviderResolutionError(
                "Canonical current Premier League season requires a start date."
            )
        try:
            canonical_start_year = date.fromisoformat(season.start_date).year
        except ValueError as error:
            raise ProviderResolutionError(
                "Canonical current Premier League season has an invalid start date."
            ) from error
        if canonical_start_year != provider_season.year:
            raise ProviderResolutionError(
                "Provider and canonical current Premier League seasons are "
                "incompatible."
            )

        returned_ids = {team.external_id for team in teams}
        expected_ids = set(self._team_mapping)
        if returned_ids != expected_ids:
            missing_ids = sorted(expected_ids - returned_ids)
            unexpected_ids = sorted(returned_ids - expected_ids)
            raise ProviderIntegrityError(
                "API-Football Premier League team collection does not match the "
                "reviewed mapping: "
                f"missing_ids={missing_ids}, unexpected_ids={unexpected_ids}."
            )

        participants: list[Participant] = []
        for external_id in sorted(returned_ids, key=int):
            participant_key = self._team_mapping[external_id]
            participant = self._participants_repository.get_by_key(
                sport_id=football.id,
                participant_key=participant_key,
            )
            if participant is None:
                raise ProviderResolutionError(
                    "Reviewed API-Football team mapping references an unknown "
                    f"canonical participant: {participant_key}."
                )
            participants.append(participant)

        if len({participant.id for participant in participants}) != len(participants):
            raise ProviderIntegrityError(
                "Reviewed API-Football team mapping contains duplicate canonical teams."
            )

        return competition, season, tuple(participants)

    def _register_data_source(self) -> DataSource:
        return register_api_football_source(
            settings=self._settings,
            repository=self._data_sources_repository,
        )

    def _planned_mappings(
        self,
        league: ApiFootballLeague,
        provider_season: ApiFootballSeason,
        teams: tuple[ApiFootballTeam, ...],
        competition: Competition,
        season: Season,
        participants: tuple[Participant, ...],
    ) -> tuple[tuple[str, int, str, dict[str, object]], ...]:
        teams_by_id = {team.external_id: team for team in teams}
        participants_by_key = {
            participant.participant_key: participant for participant in participants
        }
        planned: list[tuple[str, int, str, dict[str, object]]] = [
            (
                "competition",
                competition.id,
                league.external_id,
                {
                    "country_code": league.country_code,
                    "country_name": league.country_name,
                    "provider_name": league.name,
                    "provider_type": league.league_type,
                },
            ),
            (
                "season",
                season.id,
                provider_season.external_id,
                {
                    "end_date": provider_season.end_date.isoformat(),
                    "is_current": provider_season.is_current,
                    "start_date": provider_season.start_date.isoformat(),
                },
            ),
        ]

        for external_id, participant_key in sorted(
            self._team_mapping.items(), key=lambda item: int(item[0])
        ):
            team = teams_by_id[external_id]
            participant = participants_by_key[participant_key]
            planned.append(
                (
                    "participant",
                    participant.id,
                    external_id,
                    {
                        "code": team.code,
                        "country": team.country,
                        "logo_url": team.logo_url,
                        "provider_name": team.name,
                        "venue_city": team.venue_city,
                        "venue_name": team.venue_name,
                    },
                )
            )

        return tuple(planned)

    def _validate_mapping_conflicts(
        self,
        source_id: int,
        planned_mappings: tuple[tuple[str, int, str, dict[str, object]], ...],
    ) -> None:
        for object_type, internal_id, external_id, _metadata in planned_mappings:
            external_mapping = self._source_mappings_repository.get_by_external_id(
                source_id=source_id,
                object_type=object_type,
                external_id=external_id,
            )
            if (
                external_mapping is not None
                and external_mapping.internal_id != internal_id
            ):
                raise ProviderIntegrityError(
                    "API-Football external ID conflicts with an existing canonical "
                    f"mapping: object_type={object_type}, external_id={external_id}."
                )

            internal_mapping = self._source_mappings_repository.get_by_internal_id(
                source_id=source_id,
                object_type=object_type,
                internal_id=internal_id,
            )
            if (
                internal_mapping is not None
                and internal_mapping.external_id != external_id
            ):
                raise ProviderIntegrityError(
                    "Canonical object conflicts with an existing API-Football "
                    f"mapping: object_type={object_type}, internal_id={internal_id}."
                )

    def _upsert_mapping(
        self,
        source_id: int,
        object_type: str,
        internal_id: int,
        external_id: str,
        metadata: dict[str, object],
    ) -> SourceMapping:
        try:
            return self._source_mappings_repository.upsert(
                source_id=source_id,
                object_type=object_type,
                internal_id=internal_id,
                external_id=external_id,
                metadata=metadata,
            )
        except SourceMappingConflictError as error:
            raise ProviderIntegrityError(
                "API-Football source mapping conflicted during persistence."
            ) from error
