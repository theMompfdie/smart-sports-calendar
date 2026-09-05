import json
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from app.domain.competition_lifecycle import (
    CompetitionFormat,
    CompetitionLifecycleScope,
    FixtureLeg,
    FixtureObservationScopeKind,
    FixtureParticipantResolution,
    TournamentStageKind,
)
from app.domain.operator_notice import OPERATOR_NOTICE_METADATA_KEY, OperatorNotice


class FixtureImportDecision(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    SKIP = "SKIP"
    CANCEL = "CANCEL"
    DELETE = "DELETE"
    DEFER = "DEFER"


class FixtureImportConflictError(RuntimeError):
    """A fixture identity conflicts with an existing stable correlation."""


@dataclass(frozen=True)
class FixtureParticipantRecord:
    participant_id: int | None
    role: str
    position_number: int
    resolution: FixtureParticipantResolution


@dataclass(frozen=True)
class FixtureImportRecord:
    external_id: str
    sport_id: int
    competition_id: int
    season_id: int
    event_type: str
    title: str
    participants: tuple[FixtureParticipantRecord, ...]
    kickoff_utc: datetime | None
    kickoff_confirmed: bool
    timezone: str
    status: str
    stage: str | None
    round_name: str | None
    sequence_number: int | None
    venue_name: str | None
    city: str | None
    source_updated_at: datetime | None
    metadata: dict[str, Any] | None
    operator_notice: OperatorNotice | None = None
    stage_kind: TournamentStageKind | None = None
    tie_key: str | None = None
    leg: FixtureLeg | None = None
    event_key_prefix: str = "api_football"

    @property
    def participants_resolved(self) -> bool:
        return all(
            participant.resolution is FixtureParticipantResolution.RESOLVED
            for participant in self.participants
        )


@dataclass(frozen=True)
class FixtureImportScopeRecord:
    competition_id: int
    season_id: int
    window_start_utc: datetime | None
    window_end_utc: datetime | None
    authoritative: bool
    lifecycle: CompetitionLifecycleScope
    filtered: bool
    observation_id: str
    observed_at_utc: datetime

    @property
    def removal_eligible(self) -> bool:
        return (
            self.authoritative
            and not self.filtered
            and self.lifecycle.removal_reconciliation_supported
        )


@dataclass(frozen=True)
class FixtureImportItemResult:
    external_id: str
    event_id: int | None
    decision: FixtureImportDecision


@dataclass(frozen=True)
class FixtureImportResult:
    items: tuple[FixtureImportItemResult, ...]

    def count(self, decision: FixtureImportDecision) -> int:
        return sum(item.decision is decision for item in self.items)


class FixtureImportRepository:
    """Persists one validated provider observation as an atomic unit."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def import_observation(
        self,
        source_id: int,
        fixtures: tuple[FixtureImportRecord, ...],
        scope: FixtureImportScopeRecord,
    ) -> FixtureImportResult:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                result = self.import_in_transaction(
                    connection, source_id, fixtures, scope
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return result

    def import_in_transaction(
        self,
        connection: sqlite3.Connection,
        source_id: int,
        fixtures: tuple[FixtureImportRecord, ...],
        scope: FixtureImportScopeRecord,
        *,
        namespace: str | None = None,
    ) -> FixtureImportResult:
        """Caller owns commit/rollback, allowing manual receipt atomicity."""
        if not connection.in_transaction:
            raise FixtureImportConflictError("Import requires an active transaction.")
        self._validate_scope(connection, scope)
        stages = self._authority_stages(connection, source_id, scope, namespace)
        if stages is not None:
            if any(fixture.stage not in stages for fixture in fixtures):
                raise FixtureImportConflictError(
                    "Fixture exceeds source stage authority."
                )
            if scope.removal_eligible and (
                scope.lifecycle.scope_kind
                is FixtureObservationScopeKind.COMPLETE_SEASON
                or scope.lifecycle.stage not in stages
            ):
                raise FixtureImportConflictError(
                    "Removal exceeds source stage authority."
                )
        timestamp = scope.observed_at_utc.isoformat()
        results: list[FixtureImportItemResult] = []
        observed: set[int] = set()
        for fixture in fixtures:
            mapping = connection.execute(
                """SELECT e.* FROM source_mappings AS m
                JOIN sports_events AS e ON e.id=m.internal_id
                WHERE m.source_id=? AND m.object_type='event' AND m.external_id=?""",
                (source_id, fixture.external_id),
            ).fetchone()
            if mapping is not None and (
                mapping["competition_id"] != scope.competition_id
                or mapping["season_id"] != scope.season_id
                or (stages is not None and mapping["stage"] not in stages)
            ):
                raise FixtureImportConflictError(
                    "Mapped event exceeds source authority."
                )
            result = self._import_fixture(
                connection,
                source_id,
                fixture,
                timestamp,
                allow_correlation=namespace is None,
                authority_stages=stages,
            )
            results.append(result)
            if result.event_id is not None:
                observed.add(result.event_id)
        if scope.removal_eligible:
            results.extend(
                self._reconcile_missing(connection, source_id, observed, scope)
            )
        return FixtureImportResult(tuple(results))

    @staticmethod
    def _authority_stages(
        connection: sqlite3.Connection,
        source_id: int,
        scope: FixtureImportScopeRecord,
        namespace: str | None,
    ) -> frozenset[str] | None:
        rows = connection.execute(
            """SELECT source_id,namespace,stages_json,is_enabled
            FROM source_assignments WHERE competition_id=? AND season_id=?
            AND role='authoritative'""",
            (scope.competition_id, scope.season_id),
        ).fetchall()
        own = [
            row
            for row in rows
            if row["source_id"] == source_id
            and row["namespace"] == namespace
            and row["is_enabled"]
        ]
        if not own:
            if rows or namespace is not None:
                raise FixtureImportConflictError("No active authoritative assignment.")
            # Preserve standalone provider repository usage without assignments.
            return None
        if len(own) != 1:
            raise FixtureImportConflictError("Ambiguous authoritative assignment.")
        return (
            None
            if own[0]["stages_json"] is None
            else frozenset(json.loads(own[0]["stages_json"]))
        )

    @staticmethod
    def _validate_scope(
        connection: sqlite3.Connection,
        scope: FixtureImportScopeRecord,
    ) -> None:
        if scope.competition_id <= 0 or scope.season_id <= 0:
            raise FixtureImportConflictError(
                "Fixture import scope IDs must be positive."
            )
        if not scope.observation_id.strip():
            raise FixtureImportConflictError(
                "Fixture import observation ID must not be blank."
            )
        if (
            scope.observed_at_utc.tzinfo is None
            or scope.observed_at_utc.utcoffset() != UTC.utcoffset(scope.observed_at_utc)
        ):
            raise FixtureImportConflictError(
                "Fixture import observation time must be timezone-aware UTC."
            )
        if scope.filtered and scope.lifecycle.complete:
            raise FixtureImportConflictError(
                "A filtered fixture observation cannot declare a complete scope."
            )
        if (
            scope.lifecycle.scope_kind is FixtureObservationScopeKind.COMPLETE_SEASON
            and (scope.window_start_utc is None or scope.window_end_utc is None)
        ):
            raise FixtureImportConflictError(
                "A complete-season fixture observation requires a bounded UTC window."
            )
        for field_name, value in (
            ("window_start_utc", scope.window_start_utc),
            ("window_end_utc", scope.window_end_utc),
        ):
            if value is not None and (
                value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value)
            ):
                raise FixtureImportConflictError(
                    f"Fixture import {field_name} must be timezone-aware UTC."
                )
        if (
            scope.window_start_utc is not None
            and scope.window_end_utc is not None
            and scope.window_start_utc > scope.window_end_utc
        ):
            raise FixtureImportConflictError(
                "Fixture import window start must not follow its end."
            )
        row = connection.execute(
            """
            SELECT competition.competition_type
            FROM competitions AS competition
            JOIN seasons AS season ON season.competition_id = competition.id
            WHERE competition.id = ? AND season.id = ?
            """,
            (scope.competition_id, scope.season_id),
        ).fetchone()
        if row is None:
            raise FixtureImportConflictError(
                "Fixture import scope does not resolve to one canonical "
                "competition and season."
            )
        persisted_type = row["competition_type"]
        if persisted_type is None:
            raise FixtureImportConflictError(
                "Canonical competition format is required for fixture import."
            )
        try:
            competition_format = CompetitionFormat(persisted_type)
        except ValueError as error:
            raise FixtureImportConflictError(
                f"Canonical competition format is unknown: {persisted_type!r}."
            ) from error
        if competition_format is not scope.lifecycle.competition_format:
            raise FixtureImportConflictError(
                "Fixture import lifecycle format conflicts with the canonical "
                "competition format."
            )

    def _import_fixture(
        self,
        connection: sqlite3.Connection,
        source_id: int,
        fixture: FixtureImportRecord,
        timestamp: str,
        *,
        allow_correlation: bool = True,
        authority_stages: frozenset[str] | None = None,
    ) -> FixtureImportItemResult:
        mapping = connection.execute(
            """
            SELECT internal_id
            FROM source_mappings
            WHERE source_id = ? AND object_type = 'event' AND external_id = ?
            """,
            (source_id, fixture.external_id),
        ).fetchone()

        if not fixture.participants_resolved:
            return FixtureImportItemResult(
                external_id=fixture.external_id,
                event_id=(None if mapping is None else int(mapping["internal_id"])),
                decision=FixtureImportDecision.DEFER,
            )

        if mapping is None and allow_correlation:
            cross_source_event_id = self._find_cross_source_event(connection, fixture)
            if cross_source_event_id is not None:
                if authority_stages is not None:
                    candidate = connection.execute(
                        "SELECT stage FROM sports_events WHERE id=?",
                        (cross_source_event_id,),
                    ).fetchone()
                    if candidate["stage"] not in authority_stages:
                        raise FixtureImportConflictError("Cross-source stage conflict.")
                try:
                    connection.execute(
                        """
                        INSERT INTO source_mappings (
                            source_id, object_type, internal_id, external_id,
                            created_at, updated_at
                        ) VALUES (?, 'event', ?, ?, ?, ?)
                        """,
                        (
                            source_id,
                            cross_source_event_id,
                            fixture.external_id,
                            timestamp,
                            timestamp,
                        ),
                    )
                except sqlite3.IntegrityError as error:
                    raise FixtureImportConflictError(
                        "Cross-source fixture mapping conflicts with an existing "
                        f"identity: external_id={fixture.external_id}."
                    ) from error
                mapping = {"internal_id": cross_source_event_id}

        if mapping is None:
            if not fixture.kickoff_confirmed or fixture.kickoff_utc is None:
                return FixtureImportItemResult(
                    external_id=fixture.external_id,
                    event_id=None,
                    decision=FixtureImportDecision.DEFER,
                )
            try:
                event_id = self._create_event(connection, source_id, fixture, timestamp)
            except sqlite3.IntegrityError as error:
                raise FixtureImportConflictError(
                    "Fixture stable key conflicts with an existing identity: "
                    f"external_id={fixture.external_id}."
                ) from error
            try:
                connection.execute(
                    """
                    INSERT INTO source_mappings (
                        source_id, object_type, internal_id, external_id,
                        created_at, updated_at
                    ) VALUES (?, 'event', ?, ?, ?, ?)
                    """,
                    (source_id, event_id, fixture.external_id, timestamp, timestamp),
                )
            except sqlite3.IntegrityError as error:
                raise FixtureImportConflictError(
                    "Fixture source mapping conflicts with an existing identity: "
                    f"external_id={fixture.external_id}."
                ) from error
            self._replace_participants(connection, event_id, fixture, timestamp)
            return FixtureImportItemResult(
                external_id=fixture.external_id,
                event_id=event_id,
                decision=FixtureImportDecision.CREATE,
            )

        event_id = int(mapping["internal_id"])
        event = connection.execute(
            "SELECT * FROM sports_events WHERE id = ?",
            (event_id,),
        ).fetchone()
        if event is None:
            raise FixtureImportConflictError(
                "Fixture mapping points to a missing canonical event: "
                f"external_id={fixture.external_id}, event_id={event_id}."
            )
        expected_key = self.event_key(fixture.event_key_prefix, fixture.external_id)
        if event["event_key"] != expected_key and ":fixture:" not in event["event_key"]:
            raise FixtureImportConflictError(
                "Fixture mapping points to an event with a conflicting stable key: "
                f"external_id={fixture.external_id}, event_id={event_id}."
            )

        target = self.target_values(event, fixture)
        was_cancelled = event["status"] == "cancelled"
        is_cancelled = target["status"] == "cancelled"
        if is_cancelled:
            target["cancelled_at"] = event["cancelled_at"] or timestamp
        else:
            target["cancelled_at"] = None
        participants_changed = self._participants_changed(connection, event_id, fixture)
        changed = any(event[key] != value for key, value in target.items())
        connection.execute(
            """
            DELETE FROM fixture_reconciliation_state
            WHERE source_id = ? AND event_id = ?
            """,
            (source_id, event_id),
        )

        if not changed and not participants_changed:
            return FixtureImportItemResult(
                external_id=fixture.external_id,
                event_id=event_id,
                decision=FixtureImportDecision.SKIP,
            )

        target["last_seen_at"] = timestamp

        assignments = ", ".join(f"{column} = ?" for column in target)
        connection.execute(
            f"UPDATE sports_events SET {assignments}, updated_at = ? WHERE id = ?",
            (*target.values(), timestamp, event_id),
        )
        if participants_changed:
            self._replace_participants(connection, event_id, fixture, timestamp)

        return FixtureImportItemResult(
            external_id=fixture.external_id,
            event_id=event_id,
            decision=(
                FixtureImportDecision.CANCEL
                if is_cancelled and not was_cancelled
                else FixtureImportDecision.UPDATE
            ),
        )

    @staticmethod
    def _find_cross_source_event(
        connection: sqlite3.Connection,
        fixture: FixtureImportRecord,
    ) -> int | None:
        if len(fixture.participants) != 2:
            return None
        by_role = {
            participant.role: participant for participant in fixture.participants
        }
        home = by_role.get("home")
        away = by_role.get("away")
        if home is None or away is None:
            return None
        rows = connection.execute(
            """
            SELECT event.id
            FROM sports_events AS event
            WHERE event.sport_id = ?
              AND event.competition_id = ?
              AND event.season_id = ?
              AND event.event_type = ?
              AND EXISTS (
                  SELECT 1 FROM event_participants AS home
                  WHERE home.event_id = event.id
                    AND home.participant_id = ? AND home.role = 'home'
              )
              AND EXISTS (
                  SELECT 1 FROM event_participants AS away
                  WHERE away.event_id = event.id
                    AND away.participant_id = ? AND away.role = 'away'
              )
              AND (
                  SELECT COUNT(*) FROM event_participants AS participant
                  WHERE participant.event_id = event.id
              ) = 2
            ORDER BY event.id
            """,
            (
                fixture.sport_id,
                fixture.competition_id,
                fixture.season_id,
                fixture.event_type,
                home.participant_id,
                away.participant_id,
            ),
        ).fetchall()
        if len(rows) > 1:
            raise FixtureImportConflictError(
                "Cross-source fixture correlation is ambiguous for the declared "
                "home/away participants."
            )
        return None if not rows else int(rows[0]["id"])

    def _create_event(
        self,
        connection: sqlite3.Connection,
        source_id: int,
        fixture: FixtureImportRecord,
        timestamp: str,
    ) -> int:
        kickoff_utc = fixture.kickoff_utc
        if not fixture.kickoff_confirmed or kickoff_utc is None:
            raise ValueError(
                "A confirmed UTC kickoff is required to create a sports event."
            )
        cancelled_at = timestamp if fixture.status == "cancelled" else None
        cursor = connection.execute(
            """
            INSERT INTO sports_events (
                sport_id, competition_id, season_id, event_key, event_type,
                title, stage, round_name, sequence_number, start_time,
                timezone, venue_name, city, status, source_updated_at,
                first_seen_at, last_seen_at, cancelled_at, metadata_json,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fixture.sport_id,
                fixture.competition_id,
                fixture.season_id,
                self.event_key(fixture.event_key_prefix, fixture.external_id),
                fixture.event_type,
                fixture.title,
                fixture.stage,
                fixture.round_name,
                fixture.sequence_number,
                kickoff_utc.isoformat(),
                fixture.timezone,
                fixture.venue_name,
                fixture.city,
                fixture.status,
                self._isoformat(fixture.source_updated_at),
                timestamp,
                timestamp,
                cancelled_at,
                self._serialize_metadata(self._event_metadata(fixture)),
                timestamp,
                timestamp,
            ),
        )
        event_id = cursor.lastrowid
        if event_id is None:
            raise RuntimeError("SQLite did not return an ID for the created event.")
        return event_id

    @staticmethod
    def target_values(
        event: Mapping[str, Any] | sqlite3.Row,
        fixture: FixtureImportRecord,
    ) -> dict[str, object]:
        start_time = event["start_time"]
        if fixture.kickoff_confirmed and fixture.kickoff_utc is not None:
            start_time = fixture.kickoff_utc.isoformat()
        persisted_metadata = (
            None
            if event["metadata_json"] is None
            else json.loads(event["metadata_json"])
        )
        event_metadata = FixtureImportRepository._event_metadata(
            fixture, persisted_metadata
        )
        metadata_json = (
            FixtureImportRepository._serialize_metadata(event_metadata)
            if event_metadata is not None
            or (
                persisted_metadata is not None
                and OPERATOR_NOTICE_METADATA_KEY in persisted_metadata
                and fixture.operator_notice is None
            )
            else event["metadata_json"]
        )
        return {
            "sport_id": fixture.sport_id,
            "competition_id": fixture.competition_id,
            "season_id": fixture.season_id,
            "event_type": fixture.event_type,
            "title": fixture.title,
            "stage": fixture.stage if fixture.stage is not None else event["stage"],
            "round_name": (
                fixture.round_name
                if fixture.round_name is not None
                else event["round_name"]
            ),
            "sequence_number": (
                fixture.sequence_number
                if fixture.sequence_number is not None
                else event["sequence_number"]
            ),
            "start_time": start_time,
            "timezone": fixture.timezone,
            "venue_name": (
                fixture.venue_name
                if fixture.venue_name is not None
                else event["venue_name"]
            ),
            "city": fixture.city if fixture.city is not None else event["city"],
            "status": fixture.status,
            "source_updated_at": (
                FixtureImportRepository._isoformat(fixture.source_updated_at)
                if fixture.source_updated_at is not None
                else event["source_updated_at"]
            ),
            "last_seen_at": event["last_seen_at"],
            "deleted_at": None,
            "metadata_json": metadata_json,
        }

    def _replace_participants(
        self,
        connection: sqlite3.Connection,
        event_id: int,
        fixture: FixtureImportRecord,
        timestamp: str,
    ) -> None:
        connection.execute(
            "DELETE FROM event_participants WHERE event_id = ?",
            (event_id,),
        )
        connection.executemany(
            """
            INSERT INTO event_participants (
                event_id, participant_id, role, position_number, is_primary,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, 1, ?, ?)
            """,
            (
                (
                    event_id,
                    participant.participant_id,
                    participant.role,
                    participant.position_number,
                    timestamp,
                    timestamp,
                )
                for participant in fixture.participants
            ),
        )

    @staticmethod
    def _participants_changed(
        connection: sqlite3.Connection,
        event_id: int,
        fixture: FixtureImportRecord,
    ) -> bool:
        rows = connection.execute(
            """
            SELECT participant_id, role, position_number
            FROM event_participants
            WHERE event_id = ?
            ORDER BY position_number, participant_id, role
            """,
            (event_id,),
        ).fetchall()
        current = tuple(
            (row["participant_id"], row["role"], row["position_number"]) for row in rows
        )
        expected = tuple(
            sorted(
                [
                    (
                        participant.participant_id,
                        participant.role,
                        participant.position_number,
                    )
                    for participant in fixture.participants
                ],
                key=lambda item: (item[2], item[0], item[1]),
            )
        )
        return current != expected

    def _reconcile_missing(
        self,
        connection: sqlite3.Connection,
        source_id: int,
        observed_event_ids: set[int],
        scope: FixtureImportScopeRecord,
    ) -> list[FixtureImportItemResult]:
        timestamp = scope.observed_at_utc.isoformat()
        boundary_sql, boundary_parameters = self._reconciliation_boundary(scope)
        rows = connection.execute(
            f"""
            SELECT sm.external_id, event.*
            FROM source_mappings AS sm
            JOIN sports_events AS event ON event.id = sm.internal_id
            WHERE sm.source_id = ? AND sm.object_type = 'event'
              AND event.competition_id = ? AND event.season_id = ?
              {boundary_sql}
            ORDER BY event.id
            """,
            (
                source_id,
                scope.competition_id,
                scope.season_id,
                *boundary_parameters,
            ),
        ).fetchall()
        results: list[FixtureImportItemResult] = []
        for event in rows:
            event_id = int(event["id"])
            if event_id in observed_event_ids or not self._in_window(event, scope):
                continue
            state = connection.execute(
                """
                SELECT * FROM fixture_reconciliation_state
                WHERE source_id = ? AND event_id = ?
                """,
                (source_id, event_id),
            ).fetchone()
            if (
                state is not None
                and state["last_observation_id"] == scope.observation_id
            ):
                continue
            if (
                state is not None
                and datetime.fromisoformat(state["last_missing_at"])
                >= scope.observed_at_utc
            ):
                continue
            count = 1 if state is None else int(state["missing_observation_count"]) + 1
            first_missing_at = timestamp if state is None else state["first_missing_at"]
            connection.execute(
                """
                INSERT INTO fixture_reconciliation_state (
                    source_id, event_id, external_id, missing_observation_count,
                    first_missing_at, last_missing_at, last_observation_id,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (source_id, event_id) DO UPDATE SET
                    missing_observation_count = excluded.missing_observation_count,
                    last_missing_at = excluded.last_missing_at,
                    last_observation_id = excluded.last_observation_id,
                    updated_at = excluded.updated_at
                """,
                (
                    source_id,
                    event_id,
                    event["external_id"],
                    count,
                    first_missing_at,
                    timestamp,
                    scope.observation_id,
                    timestamp,
                    timestamp,
                ),
            )
            if count >= 2 and event["deleted_at"] is None:
                connection.execute(
                    """
                    UPDATE sports_events
                    SET deleted_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (timestamp, timestamp, event_id),
                )
                results.append(
                    FixtureImportItemResult(
                        external_id=event["external_id"],
                        event_id=event_id,
                        decision=FixtureImportDecision.DELETE,
                    )
                )
        return results

    @staticmethod
    def _reconciliation_boundary(
        scope: FixtureImportScopeRecord,
    ) -> tuple[str, tuple[str, ...]]:
        lifecycle = scope.lifecycle
        if lifecycle.scope_kind is FixtureObservationScopeKind.COMPLETE_SEASON:
            return "", ()
        if lifecycle.scope_kind is FixtureObservationScopeKind.COMPLETE_STAGE:
            if lifecycle.stage is None:
                raise FixtureImportConflictError(
                    "Complete-stage reconciliation requires a stage identifier."
                )
            return "AND event.stage = ?", (lifecycle.stage,)
        if lifecycle.scope_kind is FixtureObservationScopeKind.COMPLETE_ROUND:
            if lifecycle.round_name is None:
                raise FixtureImportConflictError(
                    "Complete-round reconciliation requires a round identifier."
                )
            if lifecycle.stage is None:
                return "AND event.round_name = ?", (lifecycle.round_name,)
            return (
                "AND event.round_name = ? AND event.stage = ?",
                (lifecycle.round_name, lifecycle.stage),
            )
        raise FixtureImportConflictError(
            "Removal reconciliation requires a complete supported lifecycle scope."
        )

    @staticmethod
    def _in_window(event: sqlite3.Row, scope: FixtureImportScopeRecord) -> bool:
        start = datetime.fromisoformat(event["start_time"])
        if scope.window_start_utc is not None and start < scope.window_start_utc:
            return False
        return not (scope.window_end_utc is not None and start > scope.window_end_utc)

    @staticmethod
    def event_key(source_key: str, external_id: str) -> str:
        return f"{source_key}:fixture:{external_id}"

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _serialize_metadata(metadata: dict[str, Any] | None) -> str | None:
        if metadata is None:
            return None
        return json.dumps(metadata, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _event_metadata(
        fixture: FixtureImportRecord,
        persisted_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        supplied_metadata = fixture.metadata
        reserved_metadata_keys = {
            "tournament_lifecycle",
            OPERATOR_NOTICE_METADATA_KEY,
        }
        if supplied_metadata is not None and reserved_metadata_keys.intersection(
            supplied_metadata
        ):
            raise FixtureImportConflictError(
                "Fixture provider metadata uses reserved tournament lifecycle "
                "or operator notice data."
            )
        metadata: dict[str, Any] = dict(
            (persisted_metadata if supplied_metadata is None else supplied_metadata)
            or {}
        )
        if (
            supplied_metadata is not None
            and persisted_metadata is not None
            and "tournament_lifecycle" in persisted_metadata
        ):
            metadata["tournament_lifecycle"] = persisted_metadata[
                "tournament_lifecycle"
            ]
        lifecycle = {
            "stage_kind": (
                None if fixture.stage_kind is None else fixture.stage_kind.value
            ),
            "tie_key": fixture.tie_key,
            "leg": None if fixture.leg is None else fixture.leg.value,
        }
        if any(value is not None for value in lifecycle.values()):
            metadata["tournament_lifecycle"] = lifecycle
        if fixture.operator_notice is not None:
            metadata[OPERATOR_NOTICE_METADATA_KEY] = fixture.operator_notice.text
        else:
            metadata.pop(OPERATOR_NOTICE_METADATA_KEY, None)
        return metadata or None

    @staticmethod
    def _isoformat(value: datetime | None) -> str | None:
        return None if value is None else value.isoformat()
