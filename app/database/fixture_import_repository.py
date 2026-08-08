import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


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
    participant_id: int
    role: str
    position_number: int


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
    metadata: dict[str, str] | None


@dataclass(frozen=True)
class FixtureImportScopeRecord:
    competition_id: int
    season_id: int
    window_start_utc: datetime | None
    window_end_utc: datetime | None
    authoritative: bool
    observation_id: str
    observed_at_utc: datetime


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
        timestamp = scope.observed_at_utc.isoformat()
        results: list[FixtureImportItemResult] = []
        observed_event_ids: set[int] = set()

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                for fixture in fixtures:
                    result = self._import_fixture(
                        connection=connection,
                        source_id=source_id,
                        fixture=fixture,
                        timestamp=timestamp,
                    )
                    results.append(result)
                    if result.event_id is not None:
                        observed_event_ids.add(result.event_id)

                if scope.authoritative:
                    results.extend(
                        self._reconcile_missing(
                            connection=connection,
                            source_id=source_id,
                            observed_event_ids=observed_event_ids,
                            scope=scope,
                        )
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

        return FixtureImportResult(items=tuple(results))

    def _import_fixture(
        self,
        connection: sqlite3.Connection,
        source_id: int,
        fixture: FixtureImportRecord,
        timestamp: str,
    ) -> FixtureImportItemResult:
        mapping = connection.execute(
            """
            SELECT internal_id
            FROM source_mappings
            WHERE source_id = ? AND object_type = 'event' AND external_id = ?
            """,
            (source_id, fixture.external_id),
        ).fetchone()

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
        expected_key = self.event_key(source_id, fixture.external_id)
        if event["event_key"] != expected_key:
            raise FixtureImportConflictError(
                "Fixture mapping points to an event with a conflicting stable key: "
                f"external_id={fixture.external_id}, event_id={event_id}."
            )

        target = self._target_values(event, fixture)
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
                self.event_key(source_id, fixture.external_id),
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
                self._serialize_metadata(fixture.metadata),
                timestamp,
                timestamp,
            ),
        )
        event_id = cursor.lastrowid
        if event_id is None:
            raise RuntimeError("SQLite did not return an ID for the created event.")
        return event_id

    def _target_values(
        self,
        event: sqlite3.Row,
        fixture: FixtureImportRecord,
    ) -> dict[str, object]:
        start_time = event["start_time"]
        if fixture.kickoff_confirmed and fixture.kickoff_utc is not None:
            start_time = fixture.kickoff_utc.isoformat()
        metadata_json = (
            self._serialize_metadata(fixture.metadata)
            if fixture.metadata is not None
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
                self._isoformat(fixture.source_updated_at)
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
        rows = connection.execute(
            """
            SELECT sm.external_id, event.*
            FROM source_mappings AS sm
            JOIN sports_events AS event ON event.id = sm.internal_id
            WHERE sm.source_id = ? AND sm.object_type = 'event'
              AND event.competition_id = ? AND event.season_id = ?
            ORDER BY event.id
            """,
            (source_id, scope.competition_id, scope.season_id),
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
    def _in_window(event: sqlite3.Row, scope: FixtureImportScopeRecord) -> bool:
        start = datetime.fromisoformat(event["start_time"])
        if scope.window_start_utc is not None and start < scope.window_start_utc:
            return False
        return not (scope.window_end_utc is not None and start > scope.window_end_utc)

    @staticmethod
    def event_key(source_id: int, external_id: str) -> str:
        del source_id
        return f"api_football:fixture:{external_id}"

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
    def _isoformat(value: datetime | None) -> str | None:
        return None if value is None else value.isoformat()
