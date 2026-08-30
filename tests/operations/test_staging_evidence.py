import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import app.operations.staging_evidence as staging_evidence
import pytest
from app.application.football_data_premier_league_service import (
    register_football_data_source,
)
from app.application.oefb_ical_competition_service import register_oefb_ical_source
from app.application.openligadb_competition_service import register_openligadb_source
from app.config.settings import (
    FootballDataSettings,
    OefbIcalSettings,
    OpenLigaDBSettings,
)
from app.database.calendar_event_mappings_repository import (
    CalendarEventMappingsRepository,
)
from app.database.competitions_catalog import initialize_competitions_catalog
from app.database.competitions_repository import CompetitionsRepository
from app.database.data_sources_repository import DataSourcesRepository
from app.database.database import Database
from app.database.seasons_catalog import initialize_seasons_catalog
from app.database.seasons_repository import SeasonsRepository
from app.database.source_assignments_repository import (
    SourceAssignmentsRepository,
    SourceAssignmentWrite,
)
from app.database.source_mappings_repository import SourceMappingsRepository
from app.database.sports_catalog import initialize_sports_catalog
from app.database.sports_events_repository import SportsEventsRepository
from app.database.sports_repository import SportsRepository
from app.database.sync_runs_repository import SyncRunsRepository
from app.operations.staging_evidence import (
    SafeAuthoritySummary,
    SafeFixtureScopeSummary,
    SafeRunSummary,
    StagingEvidence,
    StagingEvidenceValidationError,
    collect_staging_evidence,
    main,
    render_staging_evidence,
    validate_nations_league_a_candidate,
    validate_phase_5_candidate,
)
from app.providers.contracts import SourceRole


def create_database(tmp_path: Path) -> Path:
    database_path = tmp_path / "sports.db"
    database = Database(database_path)
    database.initialize()
    database.record_startup()
    return database_path


def phase_5_candidate_evidence() -> StagingEvidence:
    definitions = (
        (
            "football-data-premier-league",
            "football_data",
            "premier_league",
            "complete_season",
            True,
            True,
            380,
        ),
        (
            "football-data-bundesliga",
            "football_data",
            "bundesliga",
            "complete_season",
            True,
            True,
            306,
        ),
        (
            "football-data-championship",
            "football_data",
            "championship",
            "complete_stage",
            True,
            True,
            552,
        ),
        (
            "openligadb-dfb-pokal",
            "openligadb",
            "dfb_pokal",
            "partial",
            False,
            False,
            32,
        ),
        (
            "openligadb-second-bundesliga",
            "openligadb",
            "second_bundesliga",
            "partial",
            False,
            False,
            306,
        ),
        (
            "oefb-ical-oefb-cup",
            "oefb_ical",
            "oefb_cup",
            "partial",
            False,
            False,
            48,
        ),
    )

    return StagingEvidence(
        database_quick_check="ok",
        schema_version="008_add_calendar_sync_revisions",
        startup_records=2,
        sports_events=sum(definition[-1] for definition in definitions),
        active_authorities=tuple(
            SafeAuthoritySummary(
                job_key=job_key,
                source_key=source_key,
                sport_key="football",
                competition_key=competition_key,
                season_key="2026_27",
                role="authoritative",
                interval_seconds=21600,
            )
            for job_key, source_key, competition_key, *_ in definitions
        ),
        fixture_scopes=tuple(
            SafeFixtureScopeSummary(
                source_key=source_key,
                competition_key=competition_key,
                season_key="2026_27",
                fixtures_total=fixture_count,
                fixtures_active=fixture_count,
                fixtures_deleted=0,
                source_event_mappings=fixture_count,
                source_event_ids_sha256=str(index) * 64,
                calendar_mappings=fixture_count,
                calendar_targets=1,
                calendar_mapping_status_counts={"synced": fixture_count},
                earliest_start_utc="2026-08-01T18:00:00+00:00",
                latest_start_utc="2027-05-29T18:00:00+00:00",
                latest_source_update_utc="2026-08-19T06:00:00+00:00",
                status_counts={"scheduled": fixture_count},
            )
            for index, (
                _,
                source_key,
                competition_key,
                _,
                _,
                _,
                fixture_count,
            ) in enumerate(definitions, start=1)
        ),
        calendar_mappings_by_status={
            "synced": sum(definition[-1] for definition in definitions)
        },
        recent_runs=tuple(
            SafeRunSummary(
                id=index,
                run_type="provider_import",
                started_at="2026-08-19T06:00:00+00:00",
                finished_at="2026-08-19T06:01:00+00:00",
                status="completed",
                items_processed=fixture_count,
                items_created=0,
                items_updated=0,
                items_unchanged=fixture_count,
                items_cancelled=0,
                items_deleted=0,
                items_deferred=0,
                items_failed=0,
                source_key=source_key,
                job_key=job_key,
                competition_key=competition_key,
                season_key="2026_27",
                authoritative=True,
                complete=complete,
                scope_kind=scope_kind,
                removal_eligible=removal_eligible,
                error_category=None,
                scope_stage=(
                    "REGULAR_SEASON" if competition_key == "championship" else None
                ),
            )
            for index, (
                job_key,
                source_key,
                competition_key,
                scope_kind,
                complete,
                removal_eligible,
                fixture_count,
            ) in enumerate(definitions, start=1)
        ),
    )


def nations_league_a_candidate_evidence() -> StagingEvidence:
    phase_5 = phase_5_candidate_evidence()
    fixture_count = 48
    total_fixtures = phase_5.sports_events + fixture_count
    return replace(
        phase_5,
        sports_events=total_fixtures,
        active_authorities=(
            *phase_5.active_authorities,
            SafeAuthoritySummary(
                job_key="openligadb-uefa-nations-league",
                source_key="openligadb",
                sport_key="football",
                competition_key="uefa_nations_league",
                season_key="2026_27",
                role="authoritative",
                interval_seconds=21600,
            ),
        ),
        fixture_scopes=(
            *phase_5.fixture_scopes,
            SafeFixtureScopeSummary(
                source_key="openligadb",
                competition_key="uefa_nations_league",
                season_key="2026_27",
                fixtures_total=fixture_count,
                fixtures_active=fixture_count,
                fixtures_deleted=0,
                source_event_mappings=fixture_count,
                source_event_ids_sha256="7" * 64,
                calendar_mappings=fixture_count,
                calendar_targets=1,
                calendar_mapping_status_counts={"synced": fixture_count},
                earliest_start_utc="2026-09-24T16:00:00+00:00",
                latest_start_utc="2026-11-17T20:00:00+00:00",
                latest_source_update_utc="2026-08-30T08:00:00+00:00",
                status_counts={"scheduled": fixture_count},
                source_participant_mappings=16,
                stage_counts={"league_a_group_phase": fixture_count},
                round_counts={
                    "group-a-1": 12,
                    "group-a-2": 12,
                    "group-a-3": 12,
                    "group-a-4": 12,
                },
            ),
        ),
        calendar_mappings_by_status={"synced": total_fixtures},
        recent_runs=(
            SafeRunSummary(
                id=7,
                run_type="provider_import",
                started_at="2026-08-30T08:00:00+00:00",
                finished_at="2026-08-30T08:01:00+00:00",
                status="completed",
                items_processed=fixture_count,
                items_created=0,
                items_updated=0,
                items_unchanged=fixture_count,
                items_cancelled=0,
                items_deleted=0,
                items_deferred=0,
                items_failed=0,
                source_key="openligadb",
                job_key="openligadb-uefa-nations-league",
                competition_key="uefa_nations_league",
                season_key="2026_27",
                authoritative=True,
                complete=False,
                scope_kind="partial",
                removal_eligible=False,
                error_category=None,
                scope_stage="league_a_group_phase",
                scope_stage_kind="league_phase",
                filtered=True,
            ),
            *phase_5.recent_runs,
        ),
    )


def test_collect_staging_evidence_returns_only_safe_operational_fields(
    tmp_path: Path,
) -> None:
    database_path = create_database(tmp_path)
    repository = SyncRunsRepository(database_path)

    completed = repository.start(
        run_type="provider_import",
        metadata={"api_key": "provider-secret", "calendar_id": "calendar-secret"},
    )
    repository.complete(
        completed.id,
        items_processed=8,
        items_created=5,
        items_updated=1,
        items_unchanged=2,
        items_deleted=0,
        items_failed=0,
        metadata={
            "source_key": "openligadb",
            "job_key": "openligadb-dfb-pokal",
            "competition_key": "dfb_pokal",
            "season_key": "2026_27",
            "authoritative": True,
            "complete": False,
            "scope_kind": "partial",
            "removal_eligible": False,
            "filtered": False,
            "error_category": "ProviderNetworkError",
            "authorization": "Bearer graph-secret",
        },
    )
    failed = repository.start(run_type="calendar_sync")
    repository.fail(
        failed.id,
        error_message="request exposed-secret failed",
        metadata={"url": "https://example.invalid/?token=secret-value"},
    )

    evidence = collect_staging_evidence(database_path)
    rendered = render_staging_evidence(evidence)
    payload = json.loads(rendered)

    assert payload["database_quick_check"] == "ok"
    assert payload["schema_version"] == "008_add_calendar_sync_revisions"
    assert payload["startup_records"] == 1
    assert payload["sports_events"] == 0
    assert payload["active_authorities"] == []
    assert payload["fixture_scopes"] == []
    assert payload["calendar_mappings_by_status"] == {}
    assert payload["calendar_mappings_revision_pending"] == 0
    assert [run["run_type"] for run in payload["recent_runs"]] == [
        "calendar_sync",
        "provider_import",
    ]
    provider_run = payload["recent_runs"][1]
    assert provider_run["items_created"] == 5
    assert provider_run["source_key"] == "openligadb"
    assert provider_run["job_key"] == "openligadb-dfb-pokal"
    assert provider_run["competition_key"] == "dfb_pokal"
    assert provider_run["season_key"] == "2026_27"
    assert provider_run["authoritative"] is True
    assert provider_run["complete"] is False
    assert provider_run["scope_kind"] == "partial"
    assert provider_run["removal_eligible"] is False
    assert provider_run["filtered"] is False
    assert provider_run["error_category"] == "ProviderNetworkError"
    assert "provider-secret" not in rendered
    assert "calendar-secret" not in rendered
    assert "graph-secret" not in rendered
    assert "exposed-secret" not in rendered
    assert "secret-value" not in rendered
    assert "metadata" not in rendered
    assert "error_message" not in rendered


def test_collect_staging_evidence_reports_safe_authoritative_fixture_scope(
    tmp_path: Path,
) -> None:
    database_path = create_database(tmp_path)
    sports = SportsRepository(database_path)
    competitions = CompetitionsRepository(database_path)
    seasons = SeasonsRepository(database_path)
    sources = DataSourcesRepository(database_path)
    initialize_sports_catalog(sports)
    initialize_competitions_catalog(competitions, sports)
    initialize_seasons_catalog(seasons, competitions, sports)

    football = sports.get_by_key("football")
    assert football is not None
    premier_league = competitions.get_by_key(football.id, "premier_league")
    assert premier_league is not None
    current_seasons = seasons.get_current_for_competition(premier_league.id)
    assert len(current_seasons) == 1
    season = current_seasons[0]
    source = register_football_data_source(
        FootballDataSettings(enabled=True, api_key="provider-secret"),
        sources,
    )
    SourceAssignmentsRepository(database_path).synchronize(
        (
            SourceAssignmentWrite(
                job_key="football-data-premier-league",
                source_id=source.id,
                competition_id=premier_league.id,
                season_id=season.id,
                role=SourceRole.AUTHORITATIVE,
                interval_seconds=3600,
            ),
        )
    )
    event = SportsEventsRepository(database_path).upsert(
        sport_id=football.id,
        competition_id=premier_league.id,
        season_id=season.id,
        event_key="football-data:provider-match-secret",
        event_type="match",
        title="Secret Home vs Secret Away",
        start_time="2026-08-21T19:00:00+00:00",
        status="scheduled",
        source_updated_at="2026-07-09T01:25:00+00:00",
        metadata={"raw_provider_secret": "fixture-metadata-secret"},
    )
    SourceMappingsRepository(database_path).upsert(
        source_id=source.id,
        object_type="event",
        internal_id=event.id,
        external_id="provider-match-secret",
        source_url="https://example.invalid/secret-fixture-url",
        metadata={"raw": "mapping-metadata-secret"},
    )
    calendar_mapping = CalendarEventMappingsRepository(database_path).create_pending(
        event.id, "calendar-secret"
    )
    CalendarEventMappingsRepository(database_path).mark_synced(
        calendar_mapping.id,
        "outlook-event-secret",
        "change-key-secret",
        "content-hash-secret",
        event_revision=1,
    )

    rendered = render_staging_evidence(collect_staging_evidence(database_path))
    payload = json.loads(rendered)

    assert payload["active_authorities"] == [
        {
            "job_key": "football-data-premier-league",
            "competition_key": "premier_league",
            "interval_seconds": 3600,
            "role": "authoritative",
            "season_key": "2026_27",
            "source_key": "football_data",
            "sport_key": "football",
        }
    ]
    assert payload["fixture_scopes"] == [
        {
            "calendar_mapping_status_counts": {"synced": 1},
            "calendar_mappings": 1,
            "calendar_mappings_revision_pending": 0,
            "calendar_targets": 1,
            "competition_key": "premier_league",
            "earliest_start_utc": "2026-08-21T19:00:00+00:00",
            "fixtures_active": 1,
            "fixtures_deleted": 0,
            "fixtures_total": 1,
            "latest_source_update_utc": "2026-07-09T01:25:00+00:00",
            "latest_start_utc": "2026-08-21T19:00:00+00:00",
            "season_key": "2026_27",
            "source_event_mappings": 1,
            "source_event_ids_sha256": (
                "833a320ca5b5aec480ba4a0f953e89ee751f2fe3c136ff6e27f459df75f5f882"
            ),
            "source_participant_mappings": 0,
            "stage_counts": {},
            "round_counts": {},
            "source_key": "football_data",
            "status_counts": {"scheduled": 1},
        }
    ]
    for excluded_value in (
        "provider-secret",
        "provider-match-secret",
        "Secret Home",
        "Secret Away",
        "fixture-metadata-secret",
        "secret-fixture-url",
        "mapping-metadata-secret",
        "api.football-data.org",
        "calendar-secret",
        "outlook-event-secret",
        "change-key-secret",
        "content-hash-secret",
    ):
        assert excluded_value not in rendered


def test_collect_staging_evidence_keeps_six_authorities_isolated(
    tmp_path: Path,
) -> None:
    database_path = create_database(tmp_path)
    sports = SportsRepository(database_path)
    competitions = CompetitionsRepository(database_path)
    seasons = SeasonsRepository(database_path)
    sources = DataSourcesRepository(database_path)
    initialize_sports_catalog(sports)
    initialize_competitions_catalog(competitions, sports)
    initialize_seasons_catalog(seasons, competitions, sports)

    football = sports.get_by_key("football")
    assert football is not None
    football_data = register_football_data_source(
        FootballDataSettings(enabled=True, api_key="provider-secret"), sources
    )
    openligadb = register_openligadb_source(OpenLigaDBSettings(enabled=True), sources)
    oefb_ical = register_oefb_ical_source(
        OefbIcalSettings(
            enabled=True,
            feed_url="https://www.fussballoesterreich.at/private.ics",
        ),
        sources,
    )
    scopes = (
        ("premier_league", "football-data-premier-league", football_data.id),
        ("bundesliga", "football-data-bundesliga", football_data.id),
        ("championship", "football-data-championship", football_data.id),
        ("dfb_pokal", "openligadb-dfb-pokal", openligadb.id),
        (
            "second_bundesliga",
            "openligadb-second-bundesliga",
            openligadb.id,
        ),
        ("oefb_cup", "oefb-ical-oefb-cup", oefb_ical.id),
    )
    assignments: list[SourceAssignmentWrite] = []
    events = SportsEventsRepository(database_path)
    source_mappings = SourceMappingsRepository(database_path)
    calendar_mappings = CalendarEventMappingsRepository(database_path)

    for index, (competition_key, job_key, source_id) in enumerate(scopes, start=1):
        competition = competitions.get_by_key(football.id, competition_key)
        assert competition is not None
        season = seasons.get_by_key(competition.id, "2026_27")
        assert season is not None
        assignments.append(
            SourceAssignmentWrite(
                job_key=job_key,
                source_id=source_id,
                competition_id=competition.id,
                season_id=season.id,
                role=SourceRole.AUTHORITATIVE,
                interval_seconds=21600,
            )
        )
        event = events.upsert(
            sport_id=football.id,
            competition_id=competition.id,
            season_id=season.id,
            event_key=f"safe-event-{index}",
            event_type="match",
            title="Redacted fixture",
            start_time=f"2026-08-{20 + index:02d}T18:00:00+00:00",
            status="scheduled",
            source_updated_at="2026-08-19T06:00:00+00:00",
        )
        source_mappings.upsert(
            source_id=source_id,
            object_type="event",
            internal_id=event.id,
            external_id=f"safe-provider-id-{index}",
        )
        mapping = calendar_mappings.create_pending(event.id, "calendar-secret")
        calendar_mappings.mark_synced(
            mapping.id,
            f"outlook-secret-{index}",
            None,
            f"hash-secret-{index}",
            event_revision=1,
        )

    SourceAssignmentsRepository(database_path).synchronize(tuple(assignments))

    evidence = collect_staging_evidence(database_path)

    assert [authority.job_key for authority in evidence.active_authorities] == [
        "football-data-bundesliga",
        "football-data-championship",
        "openligadb-dfb-pokal",
        "oefb-ical-oefb-cup",
        "football-data-premier-league",
        "openligadb-second-bundesliga",
    ]
    fixture_scopes = {scope.competition_key: scope for scope in evidence.fixture_scopes}
    assert set(fixture_scopes) == {
        "premier_league",
        "bundesliga",
        "championship",
        "dfb_pokal",
        "oefb_cup",
        "second_bundesliga",
    }
    assert fixture_scopes["premier_league"].source_key == "football_data"
    assert fixture_scopes["bundesliga"].source_key == "football_data"
    assert fixture_scopes["championship"].source_key == "football_data"
    assert fixture_scopes["dfb_pokal"].source_key == "openligadb"
    assert fixture_scopes["oefb_cup"].source_key == "oefb_ical"
    assert fixture_scopes["second_bundesliga"].source_key == "openligadb"
    assert all(scope.source_event_mappings == 1 for scope in fixture_scopes.values())
    assert all(scope.calendar_mappings == 1 for scope in fixture_scopes.values())
    assert all(scope.calendar_targets == 1 for scope in fixture_scopes.values())
    assert (
        len({scope.source_event_ids_sha256 for scope in fixture_scopes.values()}) == 6
    )


def test_collect_staging_evidence_is_read_only(tmp_path: Path) -> None:
    database_path = create_database(tmp_path)

    first = collect_staging_evidence(database_path)
    second = collect_staging_evidence(database_path)

    assert first == second


def test_validate_phase_5_candidate_accepts_converged_evidence() -> None:
    validate_phase_5_candidate(phase_5_candidate_evidence())


def test_validate_phase_5_candidate_rejects_revision_drift() -> None:
    evidence = phase_5_candidate_evidence()

    with pytest.raises(
        StagingEvidenceValidationError,
        match="calendar mapping revisions are not globally converged",
    ):
        validate_phase_5_candidate(
            replace(evidence, calendar_mappings_revision_pending=1)
        )


def test_validate_phase_5_candidate_rejects_destructive_dfb_pokal_scope() -> None:
    evidence = phase_5_candidate_evidence()
    runs = tuple(
        replace(run, complete=True, removal_eligible=True)
        if run.job_key == "openligadb-dfb-pokal"
        else run
        for run in evidence.recent_runs
    )

    with pytest.raises(
        StagingEvidenceValidationError,
        match="latest provider run is invalid for dfb_pokal",
    ):
        validate_phase_5_candidate(replace(evidence, recent_runs=runs))


def test_validate_phase_5_candidate_rejects_destructive_oefb_cup_scope() -> None:
    evidence = phase_5_candidate_evidence()
    runs = tuple(
        replace(run, complete=True, removal_eligible=True)
        if run.job_key == "oefb-ical-oefb-cup"
        else run
        for run in evidence.recent_runs
    )

    with pytest.raises(
        StagingEvidenceValidationError,
        match="latest provider run is invalid for oefb_cup",
    ):
        validate_phase_5_candidate(replace(evidence, recent_runs=runs))


def test_validate_phase_5_candidate_rejects_events_outside_candidate() -> None:
    evidence = phase_5_candidate_evidence()

    with pytest.raises(
        StagingEvidenceValidationError,
        match="database contains events outside the Phase 5 candidate scopes",
    ):
        validate_phase_5_candidate(
            replace(evidence, sports_events=evidence.sports_events + 1)
        )


def test_validate_nations_league_a_candidate_accepts_converged_evidence() -> None:
    validate_nations_league_a_candidate(nations_league_a_candidate_evidence())


@pytest.mark.parametrize(
    "mutate",
    (
        lambda run: replace(run, filtered=False),
        lambda run: replace(run, complete=True),
        lambda run: replace(run, removal_eligible=True),
        lambda run: replace(run, scope_stage=None),
        lambda run: replace(run, scope_stage_kind=None),
    ),
)
def test_validate_nations_league_a_candidate_rejects_unsafe_run_scope(
    mutate: Callable[[SafeRunSummary], SafeRunSummary],
) -> None:
    evidence = nations_league_a_candidate_evidence()
    nations_run = evidence.recent_runs[0]

    with pytest.raises(
        StagingEvidenceValidationError,
        match="latest provider run is invalid",
    ):
        validate_nations_league_a_candidate(
            replace(
                evidence,
                recent_runs=(
                    mutate(nations_run),
                    *evidence.recent_runs[1:],
                ),
            )
        )


def test_validate_nations_league_a_candidate_rejects_wrong_fixture_count() -> None:
    evidence = nations_league_a_candidate_evidence()
    nations_scope = evidence.fixture_scopes[-1]

    with pytest.raises(
        StagingEvidenceValidationError,
        match="fixture count is invalid for uefa_nations_league",
    ):
        validate_nations_league_a_candidate(
            replace(
                evidence,
                fixture_scopes=(
                    *evidence.fixture_scopes[:-1],
                    replace(nations_scope, fixtures_total=47),
                ),
            )
        )


def test_validate_nations_league_a_candidate_requires_exact_authority_set() -> None:
    evidence = nations_league_a_candidate_evidence()

    with pytest.raises(
        StagingEvidenceValidationError,
        match="enabled authoritative jobs do not match the Phase 6 Nations League A",
    ):
        validate_nations_league_a_candidate(
            replace(evidence, active_authorities=evidence.active_authorities[:-1])
        )


@pytest.mark.parametrize(
    ("mutate", "message"),
    (
        (
            lambda scope: replace(scope, source_participant_mappings=15),
            "participant mapping count is invalid",
        ),
        (
            lambda scope: replace(scope, stage_counts={}),
            "stage counts are invalid",
        ),
        (
            lambda scope: replace(scope, round_counts={"group-a-1": 48}),
            "round counts are invalid",
        ),
    ),
)
def test_validate_nations_league_a_candidate_rejects_wrong_scope_aggregates(
    mutate: Callable[[SafeFixtureScopeSummary], SafeFixtureScopeSummary],
    message: str,
) -> None:
    evidence = nations_league_a_candidate_evidence()
    nations_scope = evidence.fixture_scopes[-1]

    with pytest.raises(StagingEvidenceValidationError, match=message):
        validate_nations_league_a_candidate(
            replace(
                evidence,
                fixture_scopes=(
                    *evidence.fixture_scopes[:-1],
                    mutate(nations_scope),
                ),
            )
        )


def test_collect_staging_evidence_rejects_invalid_input(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        collect_staging_evidence(tmp_path / "missing.db")

    database_path = create_database(tmp_path)
    with pytest.raises(ValueError, match="limit must be greater than zero"):
        collect_staging_evidence(database_path, limit=0)


def test_main_prints_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    database_path = create_database(tmp_path)

    result = main(["--database", str(database_path), "--limit", "1"])

    assert result == 0
    assert json.loads(capsys.readouterr().out)["database_quick_check"] == "ok"


def test_main_selects_nations_league_a_candidate_validation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = create_database(tmp_path)
    validated: list[StagingEvidence] = []
    monkeypatch.setattr(
        staging_evidence,
        "validate_nations_league_a_candidate",
        validated.append,
    )

    result = main(
        [
            "--database",
            str(database_path),
            "--validate-nations-league-a-candidate",
        ]
    )

    assert result == 0
    assert len(validated) == 1
    assert json.loads(capsys.readouterr().out)["database_quick_check"] == "ok"
