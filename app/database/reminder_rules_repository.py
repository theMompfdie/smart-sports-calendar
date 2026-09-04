"""SQLite persistence and canonical target resolution for reminder rules."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.domain.reminder_rules import (
    ReminderAction,
    ReminderRule,
    ReminderRuleError,
    ReminderRuleResolver,
    ReminderRuleSelector,
    ReminderRuleWrite,
    ReminderScope,
)


class ReminderRuleRepositoryError(ReminderRuleError):
    """A safe persistence or canonical-resolution failure."""


class ReminderRuleNotFoundError(ReminderRuleRepositoryError):
    """Raised when a current reminder rule or canonical target is absent."""


@dataclass(frozen=True)
class ReminderRuleTarget:
    scope: ReminderScope
    competition_key: str | None = None
    participant_key: str | None = None
    event_key: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "scope", ReminderScope(self.scope))
        values = (
            self.competition_key is not None,
            self.participant_key is not None,
            self.event_key is not None,
        )
        expected = {
            ReminderScope.GLOBAL: (False, False, False),
            ReminderScope.COMPETITION: (True, False, False),
            ReminderScope.PARTICIPANT: (False, True, False),
            ReminderScope.COMPETITION_PARTICIPANT: (True, True, False),
            ReminderScope.EVENT: (False, False, True),
        }[self.scope]
        if values != expected:
            raise ReminderRuleRepositoryError(
                f"Invalid canonical keys for {self.scope.value} scope."
            )
        for value in (
            self.competition_key,
            self.participant_key,
            self.event_key,
        ):
            if value is not None and (not value or value != value.strip()):
                raise ReminderRuleRepositoryError(
                    "Canonical reminder target keys must be normalized and non-empty."
                )


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ReminderRulesRepository:
    def __init__(
        self,
        database_path: Path,
        *,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.database_path = database_path
        self._clock = clock
        self._resolver = ReminderRuleResolver()

    def resolve_target(self, target: ReminderRuleTarget) -> ReminderRuleSelector:
        with self._connect() as connection:
            competition = self._resolve_optional_key(
                connection,
                table="competitions",
                key_column="competition_key",
                key=target.competition_key,
                kind="competition",
            )
            participant = self._resolve_optional_key(
                connection,
                table="participants",
                key_column="participant_key",
                key=target.participant_key,
                kind="participant",
            )
            event = self._resolve_optional_key(
                connection,
                table="sports_events",
                key_column="event_key",
                key=target.event_key,
                kind="event",
            )

        if (
            competition is not None
            and participant is not None
            and competition[1] != participant[1]
        ):
            raise ReminderRuleRepositoryError(
                "Competition and participant reminder targets must use the same sport."
            )

        return ReminderRuleSelector(
            scope=target.scope,
            competition_id=None if competition is None else competition[0],
            participant_id=None if participant is None else participant[0],
            event_id=None if event is None else event[0],
        )

    def target_for(self, rule: ReminderRule) -> ReminderRuleTarget:
        selector = rule.selector
        with self._connect() as connection:
            competition_key = self._key_for_id(
                connection,
                table="competitions",
                key_column="competition_key",
                identifier=selector.competition_id,
                kind="competition",
            )
            participant_key = self._key_for_id(
                connection,
                table="participants",
                key_column="participant_key",
                identifier=selector.participant_id,
                kind="participant",
            )
            event_key = self._key_for_id(
                connection,
                table="sports_events",
                key_column="event_key",
                identifier=selector.event_id,
                kind="event",
            )
        return ReminderRuleTarget(
            scope=selector.scope,
            competition_key=competition_key,
            participant_key=participant_key,
            event_key=event_key,
        )

    def set(self, write: ReminderRuleWrite) -> ReminderRule:
        timestamp = self._timestamp()
        selector = write.selector
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                current = self._select_current_row(connection, selector)
                presentation_changed = self._presentation_fields_changed(
                    current,
                    write,
                )
                values = (
                    None if write.action is None else write.action.value,
                    write.preferred_lead_minutes,
                    write.minimum_lead_minutes,
                    write.maximum_lead_minutes,
                    write.quiet_start,
                    write.quiet_end,
                    write.timezone,
                    write.operator_note,
                    timestamp,
                )
                if current is None:
                    cursor = connection.execute(
                        """
                        INSERT INTO reminder_rules (
                            scope, competition_id, participant_id, event_id,
                            action, preferred_lead_minutes,
                            minimum_lead_minutes, maximum_lead_minutes,
                            quiet_start, quiet_end, timezone, is_active,
                            operator_note, deleted_at, created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, NULL, ?, ?)
                        """,
                        (
                            selector.scope.value,
                            selector.competition_id,
                            selector.participant_id,
                            selector.event_id,
                            *values[:-1],
                            timestamp,
                            timestamp,
                        ),
                    )
                    rule_id = cursor.lastrowid
                    if rule_id is None:
                        raise ReminderRuleRepositoryError(
                            "Reminder rule could not be created."
                        )
                else:
                    rule_id = current["id"]
                    connection.execute(
                        """
                        UPDATE reminder_rules
                        SET action = ?,
                            preferred_lead_minutes = ?,
                            minimum_lead_minutes = ?,
                            maximum_lead_minutes = ?,
                            quiet_start = ?,
                            quiet_end = ?,
                            timezone = ?,
                            is_active = 1,
                            operator_note = ?,
                            updated_at = ?
                        WHERE id = ?
                        """,
                        (*values, rule_id),
                    )

                rule = self._get_by_id(connection, rule_id)
                if rule is None:
                    raise ReminderRuleRepositoryError(
                        "Reminder rule could not be loaded after mutation."
                    )
                self._validate_existing_event_policies(connection)
                if presentation_changed:
                    self._invalidate_presentations(
                        connection,
                        selector=selector,
                        timestamp=timestamp,
                    )
                return rule
        except sqlite3.IntegrityError as error:
            raise ReminderRuleRepositoryError(
                "Reminder rule violates a database constraint."
            ) from error

    def get_current(self, selector: ReminderRuleSelector) -> ReminderRule | None:
        with self._connect() as connection:
            row = self._select_current_row(connection, selector)
        return None if row is None else self._map_row(row)

    def list(self, *, include_deleted: bool = False) -> list[ReminderRule]:
        query = "SELECT * FROM reminder_rules"
        if not include_deleted:
            query += " WHERE deleted_at IS NULL"
        query += " ORDER BY scope, competition_id, participant_id, event_id, id"
        with self._connect() as connection:
            rows = connection.execute(query).fetchall()
        return [self._map_row(row) for row in rows]

    def disable(self, selector: ReminderRuleSelector) -> ReminderRule:
        return self._change_state(selector, delete=False)

    def delete(self, selector: ReminderRuleSelector) -> ReminderRule:
        return self._change_state(selector, delete=True)

    def applicable_rules(
        self,
        *,
        competition_id: int | None,
        participant_ids: Iterable[int],
        event_id: int,
    ) -> tuple[ReminderRule, ...]:
        participant_ids_set = set(participant_ids)
        rules = self.list()
        return tuple(
            rule
            for rule in rules
            if rule.is_active
            and self._matches_event(
                rule,
                competition_id=competition_id,
                participant_ids=participant_ids_set,
                event_id=event_id,
            )
        )

    def _change_state(
        self,
        selector: ReminderRuleSelector,
        *,
        delete: bool,
    ) -> ReminderRule:
        timestamp = self._timestamp()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = self._select_current_row(connection, selector)
            if current is None:
                raise ReminderRuleNotFoundError("Current reminder rule was not found.")
            presentation_changed = bool(current["is_active"])
            connection.execute(
                """
                UPDATE reminder_rules
                SET is_active = 0,
                    deleted_at = CASE WHEN ? THEN ? ELSE deleted_at END,
                    updated_at = ?
                WHERE id = ?
                """,
                (int(delete), timestamp, timestamp, current["id"]),
            )
            rule = self._get_by_id(connection, current["id"])
            if rule is None:
                raise ReminderRuleRepositoryError(
                    "Reminder rule could not be loaded after mutation."
                )
            self._validate_existing_event_policies(connection)
            if presentation_changed:
                self._invalidate_presentations(
                    connection,
                    selector=selector,
                    timestamp=timestamp,
                )
            return rule

    @staticmethod
    def _presentation_fields_changed(
        current: sqlite3.Row | None,
        write: ReminderRuleWrite,
    ) -> bool:
        if current is None:
            return True
        expected = (
            None if write.action is None else write.action.value,
            write.preferred_lead_minutes,
            write.minimum_lead_minutes,
            write.maximum_lead_minutes,
            write.quiet_start,
            write.quiet_end,
            write.timezone,
            1,
        )
        actual = tuple(
            current[column]
            for column in (
                "action",
                "preferred_lead_minutes",
                "minimum_lead_minutes",
                "maximum_lead_minutes",
                "quiet_start",
                "quiet_end",
                "timezone",
                "is_active",
            )
        )
        return actual != expected

    @staticmethod
    def _invalidate_presentations(
        connection: sqlite3.Connection,
        *,
        selector: ReminderRuleSelector,
        timestamp: str,
    ) -> int:
        if selector.scope is ReminderScope.GLOBAL:
            scope_filter = "1 = 1"
            parameters: tuple[object, ...] = ()
        elif selector.scope is ReminderScope.COMPETITION:
            scope_filter = "event.competition_id = ?"
            parameters = (selector.competition_id,)
        elif selector.scope is ReminderScope.PARTICIPANT:
            scope_filter = """
                EXISTS (
                    SELECT 1
                    FROM event_participants AS participant
                    WHERE participant.event_id = event.id
                      AND participant.participant_id = ?
                )
            """
            parameters = (selector.participant_id,)
        elif selector.scope is ReminderScope.COMPETITION_PARTICIPANT:
            scope_filter = """
                event.competition_id = ?
                AND EXISTS (
                    SELECT 1
                    FROM event_participants AS participant
                    WHERE participant.event_id = event.id
                      AND participant.participant_id = ?
                )
            """
            parameters = (
                selector.competition_id,
                selector.participant_id,
            )
        else:
            scope_filter = "event.id = ?"
            parameters = (selector.event_id,)

        cursor = connection.execute(
            f"""
            UPDATE calendar_event_mappings
            SET presentation_revision = presentation_revision + 1,
                updated_at = ?
            WHERE sync_status IN ('pending', 'failed', 'synced')
              AND EXISTS (
                  SELECT 1
                  FROM sports_events AS event
                  WHERE event.id = calendar_event_mappings.event_id
                    AND event.deleted_at IS NULL
                    AND ({scope_filter})
              )
            """,
            (timestamp, *parameters),
        )
        return cursor.rowcount

    def _validate_existing_event_policies(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        rules = tuple(
            self._map_row(row)
            for row in connection.execute(
                """
                SELECT * FROM reminder_rules
                WHERE is_active = 1 AND deleted_at IS NULL
                ORDER BY scope, id
                """
            ).fetchall()
        )
        event_rows = connection.execute(
            """
            SELECT event.id, event.competition_id, participant.participant_id
            FROM sports_events AS event
            LEFT JOIN event_participants AS participant
                ON participant.event_id = event.id
            WHERE event.deleted_at IS NULL
            ORDER BY event.id, participant.participant_id
            """
        ).fetchall()
        events: dict[int, tuple[int | None, set[int]]] = {}
        for row in event_rows:
            competition_id, participant_ids = events.setdefault(
                row["id"],
                (row["competition_id"], set()),
            )
            if row["participant_id"] is not None:
                participant_ids.add(row["participant_id"])
            events[row["id"]] = (competition_id, participant_ids)

        for event_id, (competition_id, participant_ids) in events.items():
            matching = tuple(
                rule
                for rule in rules
                if self._matches_event(
                    rule,
                    competition_id=competition_id,
                    participant_ids=participant_ids,
                    event_id=event_id,
                )
            )
            try:
                self._resolver.resolve(matching)
            except ReminderRuleError as error:
                raise ReminderRuleRepositoryError(
                    "Reminder rule would make an existing event policy invalid: "
                    f"{error}"
                ) from error

    @staticmethod
    def _matches_event(
        rule: ReminderRule,
        *,
        competition_id: int | None,
        participant_ids: set[int],
        event_id: int,
    ) -> bool:
        selector = rule.selector
        if selector.scope is ReminderScope.GLOBAL:
            return True
        if selector.scope is ReminderScope.COMPETITION:
            return selector.competition_id == competition_id
        if selector.scope is ReminderScope.PARTICIPANT:
            return selector.participant_id in participant_ids
        if selector.scope is ReminderScope.COMPETITION_PARTICIPANT:
            return (
                selector.competition_id == competition_id
                and selector.participant_id in participant_ids
            )
        return selector.event_id == event_id

    @staticmethod
    def _select_current_row(
        connection: sqlite3.Connection,
        selector: ReminderRuleSelector,
    ) -> sqlite3.Row | None:
        return connection.execute(
            """
            SELECT * FROM reminder_rules
            WHERE scope = ?
              AND competition_id IS ?
              AND participant_id IS ?
              AND event_id IS ?
              AND deleted_at IS NULL
            """,
            (
                selector.scope.value,
                selector.competition_id,
                selector.participant_id,
                selector.event_id,
            ),
        ).fetchone()

    @classmethod
    def _get_by_id(
        cls,
        connection: sqlite3.Connection,
        rule_id: int,
    ) -> ReminderRule | None:
        row = connection.execute(
            "SELECT * FROM reminder_rules WHERE id = ?",
            (rule_id,),
        ).fetchone()
        return None if row is None else cls._map_row(row)

    @staticmethod
    def _map_row(row: sqlite3.Row) -> ReminderRule:
        return ReminderRule(
            id=row["id"],
            selector=ReminderRuleSelector(
                scope=ReminderScope(row["scope"]),
                competition_id=row["competition_id"],
                participant_id=row["participant_id"],
                event_id=row["event_id"],
            ),
            action=(None if row["action"] is None else ReminderAction(row["action"])),
            preferred_lead_minutes=row["preferred_lead_minutes"],
            minimum_lead_minutes=row["minimum_lead_minutes"],
            maximum_lead_minutes=row["maximum_lead_minutes"],
            quiet_start=row["quiet_start"],
            quiet_end=row["quiet_end"],
            timezone=row["timezone"],
            is_active=bool(row["is_active"]),
            operator_note=row["operator_note"],
            deleted_at=row["deleted_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _resolve_optional_key(
        connection: sqlite3.Connection,
        *,
        table: str,
        key_column: str,
        key: str | None,
        kind: str,
    ) -> tuple[int, int] | None:
        if key is None:
            return None
        query = (
            f"SELECT id, sport_id FROM {table} "
            f"WHERE {key_column} = ? ORDER BY id LIMIT 2"
        )
        rows = connection.execute(
            query,
            (key,),
        ).fetchall()
        if not rows:
            raise ReminderRuleNotFoundError(f"Unknown canonical {kind} key: {key}")
        if len(rows) > 1:
            raise ReminderRuleRepositoryError(f"Ambiguous canonical {kind} key: {key}")
        return rows[0]["id"], rows[0]["sport_id"]

    @staticmethod
    def _key_for_id(
        connection: sqlite3.Connection,
        *,
        table: str,
        key_column: str,
        identifier: int | None,
        kind: str,
    ) -> str | None:
        if identifier is None:
            return None
        row = connection.execute(
            f"SELECT {key_column} FROM {table} WHERE id = ?",
            (identifier,),
        ).fetchone()
        if row is None:
            raise ReminderRuleRepositoryError(f"Canonical {kind} target disappeared.")
        return str(row[key_column])

    def _timestamp(self) -> str:
        value = self._clock()
        if value.tzinfo is None:
            raise ReminderRuleRepositoryError(
                "Reminder rule clock must be timezone-aware."
            )
        return value.astimezone(UTC).isoformat()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection
