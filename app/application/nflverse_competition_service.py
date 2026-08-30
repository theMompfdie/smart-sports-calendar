"""NFL catalog resolution and provider-neutral nflverse normalization."""

from dataclasses import dataclass
from datetime import date

from app.database.competitions_repository import CompetitionsRepository
from app.database.participants_repository import Participant, ParticipantsRepository
from app.database.seasons_repository import SeasonsRepository
from app.database.sports_repository import SportsRepository
from app.domain.competition_lifecycle import CompetitionFormat
from app.providers.contracts import (
    NormalizedFixture,
    NormalizedFixtureBatch,
    NormalizedFixtureParticipant,
    RateLimitSnapshot,
)
from app.providers.nflverse.adapter import NflverseCompetitionAdapter
from app.providers.nflverse.exceptions import NflverseIntegrityError
from app.providers.nflverse.models import NflverseGame
from app.providers.nflverse.profiles import (
    NFL_2026_REGULAR_SEASON_PROFILE,
    NflverseCompetitionProfile,
)
from app.providers.nflverse.team_mappings import NFLVERSE_TEAM_MAPPING


@dataclass(frozen=True)
class _CanonicalContext:
    sport_id: int
    competition_id: int
    season_id: int
    season_start_date: date
    season_end_date: date
    participants_by_abbreviation: dict[str, Participant]


class NflverseCompetitionService:
    def __init__(
        self,
        adapter: NflverseCompetitionAdapter,
        sports_repository: SportsRepository,
        competitions_repository: CompetitionsRepository,
        seasons_repository: SeasonsRepository,
        participants_repository: ParticipantsRepository,
        profile: NflverseCompetitionProfile = NFL_2026_REGULAR_SEASON_PROFILE,
    ) -> None:
        if adapter.profile != profile:
            raise ValueError("nflverse adapter and service profiles differ.")
        self._adapter = adapter
        self._sports_repository = sports_repository
        self._competitions_repository = competitions_repository
        self._seasons_repository = seasons_repository
        self._participants_repository = participants_repository
        self.profile = profile

    def fetch_normalized_snapshot(self) -> NormalizedFixtureBatch:
        snapshot = self._adapter.fetch_snapshot()
        context = self._resolve_catalog()
        return NormalizedFixtureBatch(
            fixtures=tuple(self._normalize(game, context) for game in snapshot.games),
            competition_id=context.competition_id,
            competition_format=CompetitionFormat.LEAGUE,
            season_id=context.season_id,
            season_start_date=context.season_start_date,
            season_end_date=context.season_end_date,
            fetched_at_utc=snapshot.fetched_at_utc,
            page_count=1,
            request_attempts=snapshot.request_attempts,
            rate_limits=RateLimitSnapshot(None, None, None, None, None),
        )

    def _resolve_catalog(self) -> _CanonicalContext:
        sport = self._sports_repository.get_by_key(self.profile.sport_key)
        if sport is None:
            raise NflverseIntegrityError(
                "Canonical American football sport is missing."
            )
        competition = self._competitions_repository.get_by_key(
            sport.id, self.profile.competition_key
        )
        if (
            competition is None
            or competition.competition_type is not CompetitionFormat.LEAGUE
        ):
            raise NflverseIntegrityError(
                "Canonical NFL competition is missing or invalid."
            )
        season = self._seasons_repository.get_by_key(
            competition.id, self.profile.season_key
        )
        if season is None or season.start_date is None or season.end_date is None:
            raise NflverseIntegrityError(
                "Canonical NFL season is missing or incomplete."
            )
        try:
            start = date.fromisoformat(season.start_date)
            end = date.fromisoformat(season.end_date)
        except ValueError as error:
            raise NflverseIntegrityError(
                "Canonical NFL season dates are invalid."
            ) from error
        if (start, end) != (
            self.profile.season_start_date,
            self.profile.season_end_date,
        ):
            raise NflverseIntegrityError(
                "Canonical NFL season dates differ from the profile."
            )
        participants: dict[str, Participant] = {}
        for abbreviation, participant_key in NFLVERSE_TEAM_MAPPING.items():
            participant = self._participants_repository.get_by_key(
                sport.id, participant_key
            )
            if participant is None:
                raise NflverseIntegrityError(
                    "Canonical NFL participant mapping is incomplete."
                )
            participants[abbreviation] = participant
        return _CanonicalContext(
            sport.id, competition.id, season.id, start, end, participants
        )

    @staticmethod
    def _normalize(game: NflverseGame, context: _CanonicalContext) -> NormalizedFixture:
        home = context.participants_by_abbreviation[game.home_team]
        away = context.participants_by_abbreviation[game.away_team]
        return NormalizedFixture(
            external_id=game.game_id,
            sport_id=context.sport_id,
            competition_id=context.competition_id,
            season_id=context.season_id,
            event_type="match",
            title=f"{home.name} vs {away.name}",
            participants=(
                NormalizedFixtureParticipant(home.id, "home", 1),
                NormalizedFixtureParticipant(away.id, "away", 2),
            ),
            kickoff_utc=game.kickoff_utc,
            kickoff_confirmed=True,
            timezone="UTC",
            status="scheduled",
            stage="regular-season",
            round_name=f"week-{game.week}",
            sequence_number=game.week,
            venue_name=None,
            city=None,
            source_updated_at=None,
            metadata={
                "provider_game_type": "REG",
                "provider_week": str(game.week),
                "provider_espn_id": game.espn,
                "provider_old_game_id": game.old_game_id,
                "provider_gsis_id": game.gsis,
                "schedule_notice": "Subject to NFL flex scheduling.",
            },
        )
