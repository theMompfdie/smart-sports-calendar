from pathlib import Path

from app.database.competitions_repository import CompetitionsRepository
from app.database.database import Database
from app.database.event_participants_repository import EventParticipantsRepository
from app.database.media_assets_repository import MediaAssetsRepository
from app.database.participants_repository import ParticipantsRepository
from app.database.sports_events_repository import SportsEventsRepository
from app.database.sports_repository import SportsRepository
from app.database.synchronization_query_repository import (
    SynchronizationQueryRepository,
)
from app.domain.media_assets import MediaAssetOwner, MediaAssetWrite, MediaOwnerType
from app.media.event_asset_selector import EventAssetSelector


def _approve(
    repository: MediaAssetsRepository,
    *,
    asset_key: str,
    owner: MediaAssetOwner,
    variant: str,
    digest: str,
) -> None:
    pending = repository.create_pending(
        MediaAssetWrite(
            asset_key=asset_key,
            owner=owner,
            variant=variant,
            mime_type="image/png",
            width=60,
            height=60,
            byte_size=100,
            sha256=digest,
            storage_path=f"assets/{digest[:2]}/{digest}.png",
            source_reference="synthetic test asset",
            license_name="MIT",
        )
    )
    repository.approve(pending.asset_key, pending.version, "operator")


def test_selector_uses_canonical_owners_roles_and_exact_final_stage(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "sports.db"
    Database(database_path).initialize()
    sport = SportsRepository(database_path).upsert("football", "Football")
    competition = CompetitionsRepository(database_path).upsert(
        sport.id,
        "test_cup",
        "Test Cup",
    )
    participants = ParticipantsRepository(database_path)
    home = participants.upsert(sport.id, "home", "team", "Home")
    away = participants.upsert(sport.id, "away", "team", "Away")
    event = SportsEventsRepository(database_path).upsert(
        sport_id=sport.id,
        competition_id=competition.id,
        event_key="cup-final",
        event_type="match",
        title="Home vs Away",
        stage="Final",
        round_name=None,
        start_time="2027-05-20T18:00:00+00:00",
        timezone="UTC",
        status="confirmed",
    )
    assignments = EventParticipantsRepository(database_path)
    assignments.upsert(event.id, home.id, "home", 1)
    assignments.upsert(event.id, away.id, "away", 2)
    assets = MediaAssetsRepository(database_path)
    _approve(
        assets,
        asset_key="competition.test_cup.logo",
        owner=MediaAssetOwner(
            MediaOwnerType.COMPETITION,
            competition_id=competition.id,
        ),
        variant="logo",
        digest="a" * 64,
    )
    _approve(
        assets,
        asset_key="team.home.logo",
        owner=MediaAssetOwner(MediaOwnerType.PARTICIPANT, participant_id=home.id),
        variant="logo",
        digest="b" * 64,
    )
    _approve(
        assets,
        asset_key="team.away.logo",
        owner=MediaAssetOwner(MediaOwnerType.PARTICIPANT, participant_id=away.id),
        variant="logo",
        digest="c" * 64,
    )
    _approve(
        assets,
        asset_key="project.trophy",
        owner=MediaAssetOwner(
            MediaOwnerType.PROJECT,
            project_key="smart_sports_calendar",
        ),
        variant="trophy",
        digest="d" * 64,
    )
    aggregate = SynchronizationQueryRepository(database_path).get_by_event_id(
        event.id,
        "calendar-1",
    )
    assert aggregate is not None

    selected = EventAssetSelector(assets).select(aggregate)

    assert set(selected) == {"competition", "home", "away", "final"}
    assert selected["competition"].asset_key == "competition.test_cup.logo"
    assert selected["home"].asset_key == "team.home.logo"
    assert selected["away"].asset_key == "team.away.logo"
    assert selected["final"].asset_key == "project.trophy"


def test_selector_does_not_treat_semifinal_as_final() -> None:
    assert EventAssetSelector._normalize("Semi-final") == "semi_final"
    assert "semi_final" not in {
        "final",
        "finals",
        "championship",
        "championship_game",
        "super_bowl",
    }
