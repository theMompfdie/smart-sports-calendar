import sqlite3
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.application.api_football_fixture_import_service import (
    ApiFootballFixtureImportService,
    FixtureImportScope,
)
from app.application.api_football_fixture_normalization_service import (
    NormalizedFixtureParticipant,
)
from app.database.data_sources_repository import DataSourcesRepository
from app.database.event_participants_repository import EventParticipantsRepository
from app.database.fixture_import_repository import (
    FixtureImportDecision,
    FixtureImportRepository,
)
from app.database.source_mappings_repository import SourceMappingsRepository
from app.database.sports_events_repository import SportsEventsRepository
from app.domain.competition_lifecycle import (
    CompetitionFormat,
    CompetitionLifecycleScope,
    FixtureLeg,
    FixtureObservationScopeKind,
    FixtureParticipantResolution,
    TournamentStageKind,
)
from app.providers.api_football.exceptions import ProviderIntegrityError

from tests.application.test_api_football_fixture_normalization_service import (
    create_context,
)

OBSERVED_AT = datetime(2026, 8, 8, 12, tzinfo=UTC)


def create_importer(database_path: Path) -> ApiFootballFixtureImportService:
    return ApiFootballFixtureImportService(
        data_sources_repository=DataSourcesRepository(database_path),
        fixture_import_repository=FixtureImportRepository(database_path),
    )


def scope(
    competition_id: int,
    season_id: int,
    observation_id: str = "observation-1",
    authoritative: bool = False,
) -> FixtureImportScope:
    lifecycle = CompetitionLifecycleScope(
        competition_format=CompetitionFormat.LEAGUE,
        scope_kind=(
            FixtureObservationScopeKind.COMPLETE_SEASON
            if authoritative
            else FixtureObservationScopeKind.PARTIAL
        ),
    )
    return FixtureImportScope(
        competition_id=competition_id,
        season_id=season_id,
        observation_id=observation_id,
        observed_at_utc=OBSERVED_AT,
        lifecycle=lifecycle,
        window_start_utc=(datetime(2026, 7, 1, tzinfo=UTC) if authoritative else None),
        window_end_utc=(
            datetime(2027, 6, 30, 23, 59, tzinfo=UTC) if authoritative else None
        ),
        authoritative=authoritative,
    )


def test_import_persists_stable_events_mappings_and_participants(
    tmp_path: Path,
) -> None:
    context = create_context(tmp_path)
    fixtures = context.service.normalize_current_premier_league()

    result = create_importer(context.database_path).import_fixtures(
        fixtures,
        scope(context.competition_id, context.season_id),
    )

    assert result.count(FixtureImportDecision.CREATE) == 9
    assert result.count(FixtureImportDecision.DEFER) == 1
    mappings = SourceMappingsRepository(context.database_path)
    events = SportsEventsRepository(context.database_path)
    participants = EventParticipantsRepository(context.database_path)
    mapping = mappings.get_by_external_id(context.source_id, "event", "900001")
    assert mapping is not None
    event = events.get_by_id(mapping.internal_id)
    assert event is not None
    assert event.event_key == "api_football:fixture:900001"
    assert event.start_time == fixtures[0].kickoff_utc.isoformat()
    participant_roles = [
        (item.role, item.position_number)
        for item in participants.get_for_event(event.id)
    ]
    assert participant_roles == [
        ("home", 1),
        ("away", 2),
    ]
    assert mappings.get_by_external_id(context.source_id, "event", "900002") is None
    with sqlite3.connect(context.database_path) as connection:
        persisted_statuses = {
            row[0] for row in connection.execute("SELECT status FROM sports_events")
        }
    assert persisted_statuses == {
        "scheduled",
        "live",
        "finished",
        "postponed",
        "cancelled",
        "suspended",
        "abandoned",
    }
    walkover_mapping = mappings.get_by_external_id(context.source_id, "event", "900010")
    assert walkover_mapping is not None
    walkover = events.get_by_id(walkover_mapping.internal_id)
    assert walkover is not None
    assert walkover.status == "cancelled"
    assert walkover.cancelled_at == OBSERVED_AT.isoformat()
    assert walkover.metadata == {
        "provider_status_code": "WO",
        "provider_status_reason": "Walkover",
    }


def test_repeated_identical_import_is_a_write_free_skip(tmp_path: Path) -> None:
    context = create_context(tmp_path)
    fixtures = context.service.normalize_current_premier_league()
    importer = create_importer(context.database_path)
    initial = scope(context.competition_id, context.season_id)
    importer.import_fixtures(fixtures, initial)
    with sqlite3.connect(context.database_path) as connection:
        before = connection.execute(
            "SELECT id, updated_at FROM sports_events ORDER BY id"
        ).fetchall()

    result = importer.import_fixtures(
        fixtures,
        replace(initial, observation_id="observation-2"),
    )

    assert result.count(FixtureImportDecision.SKIP) == 9
    assert result.count(FixtureImportDecision.DEFER) == 1
    with sqlite3.connect(context.database_path) as connection:
        after = connection.execute(
            "SELECT id, updated_at FROM sports_events ORDER BY id"
        ).fetchall()
    assert after == before


def test_confirmed_kickoff_updates_but_tbd_preserves_known_time(
    tmp_path: Path,
) -> None:
    context = create_context(tmp_path)
    fixture = context.service.normalize_current_premier_league()[0]
    importer = create_importer(context.database_path)
    import_scope = scope(context.competition_id, context.season_id)
    created = importer.import_fixtures((fixture,), import_scope).items[0]
    assert created.event_id is not None
    original_start = fixture.kickoff_utc
    assert original_start is not None
    moved = replace(
        fixture,
        kickoff_utc=original_start.replace(hour=20),
        venue_name=None,
        city=None,
    )

    moved_result = importer.import_fixtures(
        (moved,), replace(import_scope, observation_id="moved")
    )
    tbd_result = importer.import_fixtures(
        (replace(moved, kickoff_utc=None, kickoff_confirmed=False),),
        replace(import_scope, observation_id="tbd"),
    )

    assert moved_result.items[0].decision is FixtureImportDecision.UPDATE
    assert tbd_result.items[0].decision is FixtureImportDecision.SKIP
    event = SportsEventsRepository(context.database_path).get_by_id(created.event_id)
    assert event is not None
    assert event.start_time == moved.kickoff_utc.isoformat()
    assert event.venue_name == fixture.venue_name
    assert event.city == fixture.city


def test_canonical_updates_reconcile_participants_without_changing_identity(
    tmp_path: Path,
) -> None:
    context = create_context(tmp_path)
    fixtures = context.service.normalize_current_premier_league()
    fixture = fixtures[0]
    replacement_participants = (
        replace(fixtures[2].participants[0], role="home", position_number=1),
        replace(fixtures[2].participants[1], role="away", position_number=2),
    )
    importer = create_importer(context.database_path)
    import_scope = scope(context.competition_id, context.season_id)
    created = importer.import_fixtures((fixture,), import_scope).items[0]
    assert created.event_id is not None
    updated_fixture = replace(
        fixture,
        title="Updated canonical fixture title",
        round_name="Updated round",
        venue_name="Updated venue",
        participants=replacement_participants,
    )

    updated = importer.import_fixtures(
        (updated_fixture,),
        replace(import_scope, observation_id="canonical-update"),
    ).items[0]

    assert updated.decision is FixtureImportDecision.UPDATE
    assert updated.event_id == created.event_id
    event = SportsEventsRepository(context.database_path).get_by_id(created.event_id)
    assert event is not None
    assert event.event_key == "api_football:fixture:900001"
    assert event.title == updated_fixture.title
    assert event.round_name == updated_fixture.round_name
    assert event.venue_name == updated_fixture.venue_name
    participants = EventParticipantsRepository(context.database_path).get_for_event(
        created.event_id
    )
    assert [
        (item.participant_id, item.role, item.position_number) for item in participants
    ] == [
        (
            replacement_participants[0].participant_id,
            "home",
            1,
        ),
        (
            replacement_participants[1].participant_id,
            "away",
            2,
        ),
    ]


def test_unresolved_participant_defers_until_same_fixture_identity_resolves(
    tmp_path: Path,
) -> None:
    context = create_context(tmp_path)
    fixture = context.service.normalize_current_premier_league()[0]
    unresolved = replace(
        fixture,
        title="Winner of tie A vs Arsenal",
        participants=(
            NormalizedFixtureParticipant(
                None,
                "home",
                1,
                FixtureParticipantResolution.UNRESOLVED,
            ),
            fixture.participants[1],
        ),
    )
    importer = create_importer(context.database_path)
    import_scope = scope(context.competition_id, context.season_id)

    deferred = importer.import_fixtures((unresolved,), import_scope).items[0]

    assert deferred.decision is FixtureImportDecision.DEFER
    assert deferred.event_id is None
    assert (
        SourceMappingsRepository(context.database_path).get_by_external_id(
            context.source_id,
            "event",
            fixture.external_id,
        )
        is None
    )
    with sqlite3.connect(context.database_path) as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM sports_events").fetchone()[0] == 0
        )
        assert connection.execute("SELECT COUNT(*) FROM participants").fetchone()[0] > 0

    created = importer.import_fixtures(
        (fixture,),
        replace(import_scope, observation_id="participants-resolved"),
    ).items[0]

    assert created.decision is FixtureImportDecision.CREATE
    assert created.event_id is not None

    deferred_again = importer.import_fixtures(
        (unresolved,),
        replace(import_scope, observation_id="placeholder-regression"),
    ).items[0]
    assert deferred_again.decision is FixtureImportDecision.DEFER
    assert deferred_again.event_id == created.event_id
    event = SportsEventsRepository(context.database_path).get_by_id(created.event_id)
    assert event is not None
    assert event.title == fixture.title
    assert (
        len(EventParticipantsRepository(context.database_path).get_for_event(event.id))
        == 2
    )


def test_hybrid_fixture_persists_typed_lifecycle_metadata_without_new_identity(
    tmp_path: Path,
) -> None:
    context = create_context(tmp_path)
    with sqlite3.connect(context.database_path) as connection:
        connection.execute(
            "UPDATE competitions SET competition_type = ? WHERE id = ?",
            (CompetitionFormat.HYBRID_TOURNAMENT.value, context.competition_id),
        )
    fixture = replace(
        context.service.normalize_current_premier_league()[0],
        stage="qualifying",
        round_name="qualifying_round_3",
        stage_kind=TournamentStageKind.QUALIFYING,
        tie_key="qualifying_round_3_tie_17",
        leg=FixtureLeg.FIRST,
    )
    import_scope = FixtureImportScope(
        competition_id=context.competition_id,
        season_id=context.season_id,
        observation_id="hybrid-qualifying",
        observed_at_utc=OBSERVED_AT,
        lifecycle=CompetitionLifecycleScope(
            CompetitionFormat.HYBRID_TOURNAMENT,
            FixtureObservationScopeKind.PARTIAL,
            stage="qualifying",
            round_name="qualifying_round_3",
            stage_kind=TournamentStageKind.QUALIFYING,
        ),
        authoritative=True,
    )

    result = (
        create_importer(context.database_path)
        .import_fixtures(
            (fixture,),
            import_scope,
        )
        .items[0]
    )

    assert result.decision is FixtureImportDecision.CREATE
    assert result.event_id is not None
    event = SportsEventsRepository(context.database_path).get_by_id(result.event_id)
    assert event is not None
    assert event.stage == "qualifying"
    assert event.round_name == "qualifying_round_3"
    assert event.metadata is not None
    assert event.metadata["tournament_lifecycle"] == {
        "stage_kind": "qualifying",
        "tie_key": "qualifying_round_3_tie_17",
        "leg": "first",
    }


def test_provider_metadata_cannot_override_reserved_tournament_lifecycle(
    tmp_path: Path,
) -> None:
    context = create_context(tmp_path)
    fixture = replace(
        context.service.normalize_current_premier_league()[0],
        metadata={"tournament_lifecycle": {"leg": "provider-controlled"}},
    )

    with pytest.raises(ProviderIntegrityError, match="reserved tournament"):
        create_importer(context.database_path).import_fixtures(
            (fixture,),
            scope(context.competition_id, context.season_id),
        )

    with sqlite3.connect(context.database_path) as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM sports_events").fetchone()[0] == 0
        )


def test_complete_hybrid_round_rejects_mixed_stage_kind_before_writes(
    tmp_path: Path,
) -> None:
    context = create_context(tmp_path)
    fixture = replace(
        context.service.normalize_current_premier_league()[0],
        stage="knockout",
        round_name="round_of_16",
        stage_kind=TournamentStageKind.KNOCKOUT_PLAYOFF,
    )
    complete_round = FixtureImportScope(
        competition_id=context.competition_id,
        season_id=context.season_id,
        observation_id="hybrid-round-mismatch",
        observed_at_utc=OBSERVED_AT,
        lifecycle=CompetitionLifecycleScope(
            CompetitionFormat.HYBRID_TOURNAMENT,
            FixtureObservationScopeKind.COMPLETE_ROUND,
            stage="knockout",
            round_name="round_of_16",
            stage_kind=TournamentStageKind.KNOCKOUT,
        ),
        authoritative=True,
    )

    with pytest.raises(ProviderIntegrityError, match="complete-round"):
        create_importer(context.database_path).import_fixtures(
            (fixture,),
            complete_round,
        )

    with sqlite3.connect(context.database_path) as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM sports_events").fetchone()[0] == 0
        )


def test_complete_hybrid_round_reconciliation_stays_inside_exact_boundary(
    tmp_path: Path,
) -> None:
    context = create_context(tmp_path)
    with sqlite3.connect(context.database_path) as connection:
        connection.execute(
            "UPDATE competitions SET competition_type = ? WHERE id = ?",
            (CompetitionFormat.HYBRID_TOURNAMENT.value, context.competition_id),
        )
    fixtures = context.service.normalize_current_premier_league()
    round_of_16 = tuple(
        replace(
            fixture,
            stage="knockout",
            round_name="round_of_16",
            stage_kind=TournamentStageKind.KNOCKOUT,
        )
        for fixture in fixtures[:2]
    )
    knockout_playoff = replace(
        fixtures[2],
        stage="knockout_playoff",
        round_name="round_of_16",
        stage_kind=TournamentStageKind.KNOCKOUT_PLAYOFF,
    )
    importer = create_importer(context.database_path)
    initial = FixtureImportScope(
        competition_id=context.competition_id,
        season_id=context.season_id,
        observation_id="hybrid-initial",
        observed_at_utc=OBSERVED_AT,
        lifecycle=CompetitionLifecycleScope(
            CompetitionFormat.HYBRID_TOURNAMENT,
            FixtureObservationScopeKind.PARTIAL,
        ),
        authoritative=True,
    )
    importer.import_fixtures((*round_of_16, knockout_playoff), initial)
    complete_round = replace(
        initial,
        observation_id="hybrid-round-1",
        observed_at_utc=OBSERVED_AT.replace(hour=13),
        lifecycle=CompetitionLifecycleScope(
            CompetitionFormat.HYBRID_TOURNAMENT,
            FixtureObservationScopeKind.COMPLETE_ROUND,
            stage="knockout",
            round_name="round_of_16",
            stage_kind=TournamentStageKind.KNOCKOUT,
        ),
    )

    first = importer.import_fixtures(round_of_16[1:], complete_round)
    second = importer.import_fixtures(
        round_of_16[1:],
        replace(
            complete_round,
            observation_id="hybrid-round-2",
            observed_at_utc=OBSERVED_AT.replace(hour=14),
        ),
    )

    assert first.count(FixtureImportDecision.DELETE) == 0
    assert second.count(FixtureImportDecision.DELETE) == 1
    outside_mapping = SourceMappingsRepository(
        context.database_path
    ).get_by_external_id(
        context.source_id,
        "event",
        knockout_playoff.external_id,
    )
    assert outside_mapping is not None
    outside_event = SportsEventsRepository(context.database_path).get_by_id(
        outside_mapping.internal_id
    )
    assert outside_event is not None
    assert outside_event.deleted_at is None


def test_cancellation_timestamp_is_stable_and_correction_reactivates(
    tmp_path: Path,
) -> None:
    context = create_context(tmp_path)
    fixture = context.service.normalize_current_premier_league()[0]
    importer = create_importer(context.database_path)
    import_scope = scope(context.competition_id, context.season_id)
    created = importer.import_fixtures((fixture,), import_scope).items[0]
    assert created.event_id is not None
    cancelled = replace(fixture, status="cancelled")

    first = importer.import_fixtures(
        (cancelled,), replace(import_scope, observation_id="cancelled-1")
    )
    event = SportsEventsRepository(context.database_path).get_by_id(created.event_id)
    assert event is not None
    cancelled_at = event.cancelled_at
    repeated = importer.import_fixtures(
        (cancelled,), replace(import_scope, observation_id="cancelled-2")
    )
    corrected = importer.import_fixtures(
        (fixture,), replace(import_scope, observation_id="corrected")
    )

    assert first.items[0].decision is FixtureImportDecision.CANCEL
    assert repeated.items[0].decision is FixtureImportDecision.SKIP
    assert cancelled_at == OBSERVED_AT.isoformat()
    assert corrected.items[0].decision is FixtureImportDecision.UPDATE
    event = SportsEventsRepository(context.database_path).get_by_id(created.event_id)
    assert event is not None
    assert event.cancelled_at is None
    assert event.status == fixture.status


def test_authoritative_removal_requires_two_distinct_observations_and_reactivates(
    tmp_path: Path,
) -> None:
    context = create_context(tmp_path)
    fixtures = context.service.normalize_current_premier_league()
    imported = tuple(fixture for fixture in fixtures if fixture.kickoff_confirmed)
    importer = create_importer(context.database_path)
    importer.import_fixtures(
        imported,
        scope(context.competition_id, context.season_id, "initial"),
    )
    missing = imported[0]
    remaining = imported[1:]
    authoritative = scope(
        context.competition_id,
        context.season_id,
        "missing-1",
        authoritative=True,
    )

    first = importer.import_fixtures(remaining, authoritative)
    repeated = importer.import_fixtures(remaining, authoritative)
    mapping = SourceMappingsRepository(context.database_path).get_by_external_id(
        context.source_id, "event", missing.external_id
    )
    assert mapping is not None
    event = SportsEventsRepository(context.database_path).get_by_id(mapping.internal_id)
    assert event is not None
    assert event.deleted_at is None
    reappeared_before_confirmation = importer.import_fixtures(
        (missing,),
        replace(
            authoritative,
            observation_id="reappeared-before-confirmation",
            observed_at_utc=OBSERVED_AT.replace(hour=13),
            authoritative=False,
        ),
    )
    assert (
        reappeared_before_confirmation.items[0].decision is FixtureImportDecision.SKIP
    )
    with sqlite3.connect(context.database_path) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM fixture_reconciliation_state WHERE event_id = ?",
                (mapping.internal_id,),
            ).fetchone()[0]
            == 0
        )

    importer.import_fixtures(
        remaining,
        replace(
            authoritative,
            observation_id="missing-after-reappearance",
            observed_at_utc=OBSERVED_AT.replace(hour=14),
        ),
    )
    second = importer.import_fixtures(
        remaining,
        replace(
            authoritative,
            observation_id="missing-2",
            observed_at_utc=OBSERVED_AT.replace(hour=15),
        ),
    )
    event = SportsEventsRepository(context.database_path).get_by_id(mapping.internal_id)
    assert event is not None

    assert first.count(FixtureImportDecision.DELETE) == 0
    assert repeated.count(FixtureImportDecision.DELETE) == 0
    assert second.count(FixtureImportDecision.DELETE) == 1
    assert event.deleted_at == OBSERVED_AT.replace(hour=15).isoformat()

    reappeared = importer.import_fixtures(
        (missing,),
        replace(authoritative, observation_id="reappeared"),
    )
    event = SportsEventsRepository(context.database_path).get_by_id(mapping.internal_id)
    assert event is not None
    assert reappeared.items[0].decision is FixtureImportDecision.UPDATE
    assert event.deleted_at is None
    with sqlite3.connect(context.database_path) as connection:
        state_count = connection.execute(
            "SELECT COUNT(*) FROM fixture_reconciliation_state WHERE event_id = ?",
            (mapping.internal_id,),
        ).fetchone()[0]
    assert state_count == 0


def test_partial_or_filtered_observations_cannot_remove_events(tmp_path: Path) -> None:
    context = create_context(tmp_path)
    fixtures = tuple(
        fixture
        for fixture in context.service.normalize_current_premier_league()
        if fixture.kickoff_confirmed
    )
    importer = create_importer(context.database_path)
    importer.import_fixtures(
        fixtures,
        scope(context.competition_id, context.season_id),
    )

    importer.import_fixtures(
        fixtures[1:],
        FixtureImportScope(
            competition_id=context.competition_id,
            season_id=context.season_id,
            observation_id="partial",
            observed_at_utc=OBSERVED_AT,
            lifecycle=CompetitionLifecycleScope(
                competition_format=CompetitionFormat.LEAGUE,
                scope_kind=FixtureObservationScopeKind.PARTIAL,
            ),
            authoritative=True,
            filtered=True,
        ),
    )
    with sqlite3.connect(context.database_path) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM fixture_reconciliation_state"
            ).fetchone()[0]
            == 0
        )

    with pytest.raises(ValueError, match="filtered.*complete"):
        FixtureImportScope(
            competition_id=context.competition_id,
            season_id=context.season_id,
            observation_id="unsafe",
            observed_at_utc=OBSERVED_AT,
            lifecycle=CompetitionLifecycleScope(
                competition_format=CompetitionFormat.LEAGUE,
                scope_kind=FixtureObservationScopeKind.COMPLETE_SEASON,
            ),
            window_start_utc=datetime(2026, 7, 1, tzinfo=UTC),
            window_end_utc=datetime(2027, 6, 30, tzinfo=UTC),
            authoritative=True,
            filtered=True,
        )

    kickoff = fixtures[0].kickoff_utc
    assert kickoff is not None
    with pytest.raises(ProviderIntegrityError, match="UTC import window"):
        importer.import_fixtures(
            (fixtures[0],),
            FixtureImportScope(
                competition_id=context.competition_id,
                season_id=context.season_id,
                observation_id="outside-window",
                observed_at_utc=OBSERVED_AT,
                lifecycle=CompetitionLifecycleScope(
                    competition_format=CompetitionFormat.LEAGUE,
                    scope_kind=FixtureObservationScopeKind.PARTIAL,
                ),
                window_start_utc=kickoff.replace(year=kickoff.year + 1),
            ),
        )


def test_complete_round_removal_is_bounded_and_requires_distinct_observations(
    tmp_path: Path,
) -> None:
    context = create_context(tmp_path)
    fixtures = tuple(
        fixture
        for fixture in context.service.normalize_current_premier_league()
        if fixture.kickoff_confirmed
    )
    with sqlite3.connect(context.database_path) as connection:
        connection.execute(
            "UPDATE competitions SET competition_type = ? WHERE id = ?",
            (CompetitionFormat.KNOCKOUT_CUP.value, context.competition_id),
        )
    round_of_16 = tuple(
        replace(fixture, stage="knockout", round_name="round_of_16")
        for fixture in fixtures[:2]
    )
    other_stage = replace(fixtures[2], stage="qualifying", round_name="round_of_16")
    quarterfinal = replace(fixtures[3], stage="knockout", round_name="quarterfinal")
    importer = create_importer(context.database_path)
    partial_scope = FixtureImportScope(
        competition_id=context.competition_id,
        season_id=context.season_id,
        observation_id="cup-initial",
        observed_at_utc=OBSERVED_AT,
        lifecycle=CompetitionLifecycleScope(
            competition_format=CompetitionFormat.KNOCKOUT_CUP,
            scope_kind=FixtureObservationScopeKind.PARTIAL,
        ),
        authoritative=True,
    )
    importer.import_fixtures((*round_of_16, other_stage, quarterfinal), partial_scope)
    missing = round_of_16[0]
    complete_round_scope = FixtureImportScope(
        competition_id=context.competition_id,
        season_id=context.season_id,
        observation_id="cup-round-1",
        observed_at_utc=OBSERVED_AT.replace(hour=13),
        lifecycle=CompetitionLifecycleScope(
            competition_format=CompetitionFormat.KNOCKOUT_CUP,
            scope_kind=FixtureObservationScopeKind.COMPLETE_ROUND,
            stage="knockout",
            round_name="round_of_16",
        ),
        authoritative=True,
    )

    first = importer.import_fixtures(round_of_16[1:], complete_round_scope)
    replay = importer.import_fixtures(round_of_16[1:], complete_round_scope)
    second = importer.import_fixtures(
        round_of_16[1:],
        replace(
            complete_round_scope,
            observation_id="cup-round-2",
            observed_at_utc=OBSERVED_AT.replace(hour=14),
        ),
    )

    mapping = SourceMappingsRepository(context.database_path).get_by_external_id(
        context.source_id,
        "event",
        missing.external_id,
    )
    assert mapping is not None
    event = SportsEventsRepository(context.database_path).get_by_id(mapping.internal_id)
    assert event is not None
    assert first.count(FixtureImportDecision.DELETE) == 0
    assert replay.count(FixtureImportDecision.DELETE) == 0
    assert second.count(FixtureImportDecision.DELETE) == 1
    assert event.deleted_at == OBSERVED_AT.replace(hour=14).isoformat()
    for outside_scope in (other_stage, quarterfinal):
        outside_mapping = SourceMappingsRepository(
            context.database_path
        ).get_by_external_id(
            context.source_id,
            "event",
            outside_scope.external_id,
        )
        assert outside_mapping is not None
        outside_event = SportsEventsRepository(context.database_path).get_by_id(
            outside_mapping.internal_id
        )
        assert outside_event is not None
        assert outside_event.deleted_at is None
    with sqlite3.connect(context.database_path) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM fixture_reconciliation_state"
            ).fetchone()[0]
            == 1
        )

    reappeared = importer.import_fixtures(
        round_of_16,
        replace(
            complete_round_scope,
            observation_id="cup-round-reappeared",
            observed_at_utc=OBSERVED_AT.replace(hour=15),
        ),
    )
    event = SportsEventsRepository(context.database_path).get_by_id(mapping.internal_id)
    assert event is not None
    assert reappeared.items[0].decision is FixtureImportDecision.UPDATE
    assert event.deleted_at is None


def test_complete_stage_reconciles_all_rounds_inside_only_that_stage(
    tmp_path: Path,
) -> None:
    context = create_context(tmp_path)
    fixtures = tuple(
        fixture
        for fixture in context.service.normalize_current_premier_league()
        if fixture.kickoff_confirmed
    )
    with sqlite3.connect(context.database_path) as connection:
        connection.execute(
            "UPDATE competitions SET competition_type = ? WHERE id = ?",
            (CompetitionFormat.KNOCKOUT_CUP.value, context.competition_id),
        )
    group_stage = (
        replace(fixtures[0], stage="group_stage", round_name="group_round_1"),
        replace(fixtures[1], stage="group_stage", round_name="group_round_2"),
    )
    knockout = replace(fixtures[2], stage="knockout", round_name="round_of_16")
    importer = create_importer(context.database_path)
    importer.import_fixtures(
        (*group_stage, knockout),
        FixtureImportScope(
            competition_id=context.competition_id,
            season_id=context.season_id,
            observation_id="cup-stage-initial",
            observed_at_utc=OBSERVED_AT,
            lifecycle=CompetitionLifecycleScope(
                competition_format=CompetitionFormat.KNOCKOUT_CUP,
                scope_kind=FixtureObservationScopeKind.PARTIAL,
            ),
            authoritative=True,
        ),
    )
    complete_stage = FixtureImportScope(
        competition_id=context.competition_id,
        season_id=context.season_id,
        observation_id="cup-stage-1",
        observed_at_utc=OBSERVED_AT.replace(hour=13),
        lifecycle=CompetitionLifecycleScope(
            competition_format=CompetitionFormat.KNOCKOUT_CUP,
            scope_kind=FixtureObservationScopeKind.COMPLETE_STAGE,
            stage="group_stage",
        ),
        authoritative=True,
    )

    importer.import_fixtures(group_stage[1:], complete_stage)
    result = importer.import_fixtures(
        group_stage[1:],
        replace(
            complete_stage,
            observation_id="cup-stage-2",
            observed_at_utc=OBSERVED_AT.replace(hour=14),
        ),
    )

    assert result.count(FixtureImportDecision.DELETE) == 1
    knockout_mapping = SourceMappingsRepository(
        context.database_path
    ).get_by_external_id(context.source_id, "event", knockout.external_id)
    assert knockout_mapping is not None
    knockout_event = SportsEventsRepository(context.database_path).get_by_id(
        knockout_mapping.internal_id
    )
    assert knockout_event is not None
    assert knockout_event.deleted_at is None


def test_non_authoritative_complete_round_cannot_create_removal_evidence(
    tmp_path: Path,
) -> None:
    context = create_context(tmp_path)
    fixtures = tuple(
        replace(fixture, stage="knockout", round_name="round_of_16")
        for fixture in context.service.normalize_current_premier_league()[:2]
    )
    with sqlite3.connect(context.database_path) as connection:
        connection.execute(
            "UPDATE competitions SET competition_type = ? WHERE id = ?",
            (CompetitionFormat.KNOCKOUT_CUP.value, context.competition_id),
        )
    importer = create_importer(context.database_path)
    partial_scope = FixtureImportScope(
        competition_id=context.competition_id,
        season_id=context.season_id,
        observation_id="cup-non-authoritative-initial",
        observed_at_utc=OBSERVED_AT,
        lifecycle=CompetitionLifecycleScope(
            competition_format=CompetitionFormat.KNOCKOUT_CUP,
            scope_kind=FixtureObservationScopeKind.PARTIAL,
        ),
        authoritative=True,
    )
    importer.import_fixtures(fixtures, partial_scope)
    complete_round = FixtureImportScope(
        competition_id=context.competition_id,
        season_id=context.season_id,
        observation_id="cup-non-authoritative-1",
        observed_at_utc=OBSERVED_AT.replace(hour=13),
        lifecycle=CompetitionLifecycleScope(
            competition_format=CompetitionFormat.KNOCKOUT_CUP,
            scope_kind=FixtureObservationScopeKind.COMPLETE_ROUND,
            stage="knockout",
            round_name="round_of_16",
        ),
        authoritative=False,
    )

    importer.import_fixtures(fixtures[1:], complete_round)
    importer.import_fixtures(
        fixtures[1:],
        replace(
            complete_round,
            observation_id="cup-non-authoritative-2",
            observed_at_utc=OBSERVED_AT.replace(hour=14),
        ),
    )

    with sqlite3.connect(context.database_path) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM fixture_reconciliation_state"
            ).fetchone()[0]
            == 0
        )


@pytest.mark.parametrize(
    ("fixtures", "scope_kind", "stage", "round_name", "message"),
    [
        (
            (),
            FixtureObservationScopeKind.COMPLETE_STAGE,
            "group_stage",
            None,
            "contain",
        ),
        (
            (),
            FixtureObservationScopeKind.COMPLETE_ROUND,
            None,
            "round_of_16",
            "contain",
        ),
        (
            ("wrong-stage",),
            FixtureObservationScopeKind.COMPLETE_STAGE,
            "group_stage",
            None,
            "complete-stage",
        ),
        (
            ("wrong-round",),
            FixtureObservationScopeKind.COMPLETE_ROUND,
            "knockout",
            "round_of_16",
            "complete-round",
        ),
    ],
)
def test_complete_cup_scope_rejects_empty_or_mixed_observations(
    tmp_path: Path,
    fixtures: tuple[str, ...],
    scope_kind: FixtureObservationScopeKind,
    stage: str | None,
    round_name: str | None,
    message: str,
) -> None:
    context = create_context(tmp_path)
    fixture = context.service.normalize_current_premier_league()[0]
    supplied = tuple(
        replace(fixture, external_id=f"cup-{value}", stage=value, round_name=value)
        for value in fixtures
    )
    cup_scope = FixtureImportScope(
        competition_id=context.competition_id,
        season_id=context.season_id,
        observation_id="invalid-cup-scope",
        observed_at_utc=OBSERVED_AT,
        lifecycle=CompetitionLifecycleScope(
            competition_format=CompetitionFormat.KNOCKOUT_CUP,
            scope_kind=scope_kind,
            stage=stage,
            round_name=round_name,
        ),
        authoritative=True,
    )

    with pytest.raises(ProviderIntegrityError, match=message):
        create_importer(context.database_path).import_fixtures(supplied, cup_scope)

    with sqlite3.connect(context.database_path) as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM sports_events").fetchone()[0] == 0
        )


def test_import_scope_format_must_match_canonical_competition(tmp_path: Path) -> None:
    context = create_context(tmp_path)
    fixture = context.service.normalize_current_premier_league()[0]
    import_scope = FixtureImportScope(
        competition_id=context.competition_id,
        season_id=context.season_id,
        observation_id="wrong-format",
        observed_at_utc=OBSERVED_AT,
        lifecycle=CompetitionLifecycleScope(
            competition_format=CompetitionFormat.KNOCKOUT_CUP,
            scope_kind=FixtureObservationScopeKind.PARTIAL,
        ),
    )

    with pytest.raises(ProviderIntegrityError, match="lifecycle format conflicts"):
        create_importer(context.database_path).import_fixtures(
            (fixture,),
            import_scope,
        )


def test_mapping_conflict_fails_without_changing_existing_event(tmp_path: Path) -> None:
    context = create_context(tmp_path)
    fixture = context.service.normalize_current_premier_league()[0]
    events = SportsEventsRepository(context.database_path)
    existing = events.upsert(
        sport_id=fixture.sport_id,
        competition_id=fixture.competition_id,
        season_id=fixture.season_id,
        event_key="manual-event",
        event_type="match",
        title="Manual event",
        start_time=fixture.kickoff_utc.isoformat(),
    )
    context.mappings.upsert(
        context.source_id, "event", existing.id, fixture.external_id
    )

    with pytest.raises(ProviderIntegrityError, match="conflicting stable key"):
        create_importer(context.database_path).import_fixtures(
            (fixture,), scope(context.competition_id, context.season_id)
        )

    assert events.get_by_id(existing.id) == existing


def test_failed_participant_write_rolls_back_event_and_mapping(tmp_path: Path) -> None:
    context = create_context(tmp_path)
    fixture = context.service.normalize_current_premier_league()[0]
    invalid = replace(
        fixture,
        external_id="new-invalid-fixture",
        participants=(
            NormalizedFixtureParticipant(999999, "home", 1),
            fixture.participants[1],
        ),
    )

    with pytest.raises(sqlite3.IntegrityError):
        create_importer(context.database_path).import_fixtures(
            (invalid,), scope(context.competition_id, context.season_id)
        )

    with sqlite3.connect(context.database_path) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM sports_events WHERE event_key = ?",
                ("api_football:fixture:new-invalid-fixture",),
            ).fetchone()[0]
            == 0
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM source_mappings WHERE external_id = ?",
                ("new-invalid-fixture",),
            ).fetchone()[0]
            == 0
        )
