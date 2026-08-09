from dataclasses import dataclass
from datetime import date

from app.config.settings import FootballDataSettings
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
from app.providers.contracts import (
    NormalizedFixture,
    NormalizedFixtureBatch,
    NormalizedFixtureParticipant,
)
from app.providers.football_data.adapter import FootballDataPremierLeagueAdapter
from app.providers.football_data.exceptions import (
    FootballDataIntegrityError,
    FootballDataResolutionError,
)
from app.providers.football_data.models import FootballDataMatch, FootballDataSnapshot
from app.providers.football_data.team_mappings import (
    PREMIER_LEAGUE_TEAM_NAME_MAPPING,
    resolve_team_key,
)

FOOTBALL_DATA_SOURCE_KEY = "football_data"


def register_football_data_source(
    settings: FootballDataSettings,
    repository: DataSourcesRepository,
) -> DataSource:
    return repository.upsert(
        source_key=FOOTBALL_DATA_SOURCE_KEY,
        name="football-data.org",
        base_url=settings.base_url,
        is_active=settings.enabled,
        metadata={
            "api_version_family": "v4",
            "authentication": "X-Auth-Token",
            "attribution": "Football data provided by the Football-Data.org API",
            "provider": "football-data.org",
        },
    )


@dataclass(frozen=True)
class _CanonicalContext:
    source_id: int
    sport_id: int
    competition_id: int
    season_id: int
    season_start_date: date
    season_end_date: date
    participants_by_provider_id: dict[int, Participant]


class FootballDataPremierLeagueService:
    def __init__(
        self,
        settings: FootballDataSettings,
        adapter: FootballDataPremierLeagueAdapter,
        sports_repository: SportsRepository,
        competitions_repository: CompetitionsRepository,
        seasons_repository: SeasonsRepository,
        participants_repository: ParticipantsRepository,
        season_participants_repository: SeasonParticipantsRepository,
        data_sources_repository: DataSourcesRepository,
        source_mappings_repository: SourceMappingsRepository,
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

    def fetch_normalized_snapshot(self) -> NormalizedFixtureBatch:
        season = self._resolve_current_season()
        if season.start_date is None:
            raise FootballDataResolutionError("Canonical season requires a start date.")
        try:
            season_year = date.fromisoformat(season.start_date).year
        except ValueError as error:
            raise FootballDataResolutionError(
                "Canonical season has an invalid start date."
            ) from error
        snapshot = self._adapter.fetch_snapshot(season_year)
        context = self._map_catalog(snapshot)
        return NormalizedFixtureBatch(
            fixtures=tuple(
                self._normalize_match(match, context) for match in snapshot.matches
            ),
            competition_id=context.competition_id,
            season_id=context.season_id,
            season_start_date=context.season_start_date,
            season_end_date=context.season_end_date,
            fetched_at_utc=snapshot.fetched_at_utc,
            page_count=1,
            request_attempts=snapshot.request_attempts,
            rate_limits=snapshot.rate_limits,
        )

    def _resolve_current_season(self):
        football = self._sports_repository.get_by_key("football")
        if football is None:
            raise FootballDataResolutionError("Canonical football sport is missing.")
        competition = self._competitions_repository.get_by_key(
            sport_id=football.id, competition_key="premier_league"
        )
        if competition is None:
            raise FootballDataResolutionError("Canonical Premier League is missing.")
        seasons = self._seasons_repository.get_current_for_competition(competition.id)
        if len(seasons) != 1:
            raise FootballDataResolutionError(
                "Canonical Premier League must have exactly one current season."
            )
        return seasons[0]

    def _map_catalog(self, snapshot: FootballDataSnapshot) -> _CanonicalContext:
        football = self._sports_repository.get_by_key("football")
        if football is None:
            raise FootballDataResolutionError("Canonical football sport is missing.")
        competition = self._competitions_repository.get_by_key(
            sport_id=football.id, competition_key="premier_league"
        )
        if competition is None:
            raise FootballDataResolutionError("Canonical Premier League is missing.")
        seasons = self._seasons_repository.get_current_for_competition(competition.id)
        if len(seasons) != 1:
            raise FootballDataResolutionError(
                "Canonical Premier League must have exactly one current season."
            )
        season = seasons[0]
        if season.start_date is None or season.end_date is None:
            raise FootballDataResolutionError("Canonical season dates are incomplete.")
        try:
            start_date = date.fromisoformat(season.start_date)
            end_date = date.fromisoformat(season.end_date)
        except ValueError as error:
            raise FootballDataResolutionError(
                "Canonical season dates are invalid."
            ) from error
        if (start_date, end_date) != (
            snapshot.season_start_date,
            snapshot.season_end_date,
        ):
            raise FootballDataIntegrityError(
                "Provider and canonical Premier League season dates differ."
            )

        participants_by_provider_id: dict[int, Participant] = {}
        resolved_team_keys: set[str] = set()
        for team in snapshot.teams:
            participant_key = resolve_team_key(team.name)
            if participant_key is None:
                raise FootballDataIntegrityError(
                    "Provider team name does not match the reviewed 2026/27 mapping."
                )
            resolved_team_keys.add(participant_key)
            participant = self._participants_repository.get_by_key(
                sport_id=football.id, participant_key=participant_key
            )
            if participant is None:
                raise FootballDataResolutionError(
                    "Reviewed provider team mapping references an unknown participant."
                )
            participants_by_provider_id[team.id] = participant
        if (
            len(
                {participant.id for participant in participants_by_provider_id.values()}
            )
            != 20
        ):
            raise FootballDataIntegrityError(
                "Provider team mapping does not resolve to 20 distinct participants."
            )
        if resolved_team_keys != set(PREMIER_LEAGUE_TEAM_NAME_MAPPING.values()):
            raise FootballDataIntegrityError(
                "Provider team collection does not cover the reviewed 2026/27 teams."
            )
        source = register_football_data_source(
            self._settings, self._data_sources_repository
        )
        self._upsert_mapping(
            source.id,
            "competition",
            competition.id,
            str(snapshot.competition_id),
            {"provider_code": snapshot.competition_code},
        )
        self._upsert_mapping(
            source.id,
            "season",
            season.id,
            str(snapshot.season_id),
            {"end_date": end_date.isoformat(), "start_date": start_date.isoformat()},
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
                    "provider_tla": team.tla,
                },
            )
            self._season_participants_repository.upsert(
                season_id=season.id, participant_id=participant.id
            )
        return _CanonicalContext(
            source_id=source.id,
            sport_id=football.id,
            competition_id=competition.id,
            season_id=season.id,
            season_start_date=start_date,
            season_end_date=end_date,
            participants_by_provider_id=participants_by_provider_id,
        )

    def _normalize_match(
        self, match: FootballDataMatch, context: _CanonicalContext
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
            stage=match.stage,
            round_name=(f"Matchday {match.matchday}" if match.matchday else None),
            sequence_number=match.matchday,
            venue_name=None,
            city=None,
            source_updated_at=match.source_updated_at,
            metadata={"provider_status": match.provider_status},
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
            raise FootballDataIntegrityError(
                "football-data.org mapping conflicts with an existing source mapping."
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
            raise FootballDataIntegrityError(
                "football-data.org mapping conflicted during persistence."
            ) from error
