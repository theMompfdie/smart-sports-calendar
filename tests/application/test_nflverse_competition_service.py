from datetime import UTC, datetime

import pytest
from app.application.nflverse_competition_service import NflverseCompetitionService
from app.database.competitions_catalog import initialize_competitions_catalog
from app.database.competitions_repository import CompetitionsRepository
from app.database.database import Database
from app.database.participants_catalog import initialize_participants_catalog
from app.database.participants_repository import ParticipantsRepository
from app.database.season_participants_repository import SeasonParticipantsRepository
from app.database.seasons_catalog import initialize_seasons_catalog
from app.database.seasons_repository import SeasonsRepository
from app.database.sports_catalog import initialize_sports_catalog
from app.database.sports_repository import SportsRepository
from app.providers.nflverse.exceptions import NflverseIntegrityError
from app.providers.nflverse.models import parse_snapshot
from app.providers.nflverse.profiles import NFL_2026_REGULAR_SEASON_PROFILE

from tests.providers.nflverse.support import csv_bytes


class Adapter:
    profile = NFL_2026_REGULAR_SEASON_PROFILE

    def fetch_snapshot(self):
        return parse_snapshot(
            csv_bytes(),
            profile=self.profile,
            fetched_at_utc=datetime(2026, 8, 30, tzinfo=UTC),
            request_attempts=1,
        )


def service(tmp_path):
    path = tmp_path / "sports.db"
    Database(path).initialize()
    sports = SportsRepository(path)
    competitions = CompetitionsRepository(path)
    seasons = SeasonsRepository(path)
    participants = ParticipantsRepository(path)
    memberships = SeasonParticipantsRepository(path)
    initialize_sports_catalog(sports)
    initialize_competitions_catalog(competitions, sports)
    initialize_seasons_catalog(seasons, competitions, sports)
    initialize_participants_catalog(
        participants, memberships, sports, competitions, seasons
    )
    return NflverseCompetitionService(
        Adapter(), sports, competitions, seasons, participants
    ), (sports, competitions, seasons, participants)


def test_service_normalizes_exact_nfl_scope_with_stable_identity(tmp_path) -> None:
    target, repositories = service(tmp_path)
    batch = target.fetch_normalized_snapshot()
    sports, competitions, seasons, _ = repositories
    sport = sports.get_by_key("american_football")
    assert sport is not None
    competition = competitions.get_by_key(sport.id, "nfl")
    assert competition is not None
    season = seasons.get_by_key(competition.id, "2026")
    assert season is not None
    assert len(batch.fixtures) == 272
    assert batch.competition_id == competition.id
    assert batch.season_id == season.id
    fixture = batch.fixtures[0]
    assert fixture.external_id.startswith("2026_")
    assert fixture.status == "scheduled"
    assert fixture.stage == "regular-season"
    assert fixture.round_name.startswith("week-")
    assert fixture.operator_notice is not None
    assert fixture.operator_notice.text == "Subject to NFL flex scheduling."
    assert fixture.metadata is not None
    assert "schedule_notice" not in fixture.metadata
    assert all(item.participants_resolved for item in batch.fixtures)


def test_service_fails_closed_when_canonical_participant_is_missing(tmp_path) -> None:
    target, repositories = service(tmp_path)
    sport = repositories[0].get_by_key("american_football")
    assert sport is not None
    with repositories[3]._connect() as connection:  # noqa: SLF001
        connection.execute(
            """
            DELETE FROM season_participants
            WHERE participant_id = (
                SELECT id FROM participants
                WHERE sport_id = ? AND participant_key = ?
            )
            """,
            (sport.id, "arizona_cardinals"),
        )
        connection.execute(
            "DELETE FROM participants WHERE sport_id = ? AND participant_key = ?",
            (sport.id, "arizona_cardinals"),
        )
    with pytest.raises(NflverseIntegrityError, match="mapping is incomplete"):
        target.fetch_normalized_snapshot()
