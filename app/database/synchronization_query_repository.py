import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.database.calendar_event_mappings_repository import CalendarEventMapping
from app.database.competitions_repository import Competition
from app.database.event_results_repository import EventResult
from app.database.event_statistics_repository import EventStatistic
from app.database.participants_repository import Participant
from app.database.seasons_repository import Season
from app.database.sports_events_repository import SportsEvent
from app.database.sports_repository import Sport
from app.domain.operator_notice import OPERATOR_NOTICE_METADATA_KEY, OperatorNotice


@dataclass(frozen=True)
class SynchronizationParticipant:
    participant: Participant
    role: str
    position_number: int | None
    is_primary: bool
    metadata: dict[str, Any] | None


@dataclass(frozen=True)
class SynchronizationEvent:
    event: SportsEvent
    sport: Sport
    competition: Competition | None
    season: Season | None
    parent_event: SportsEvent | None
    participants: tuple[SynchronizationParticipant, ...]
    results: tuple[EventResult, ...]
    statistics: tuple[EventStatistic, ...]
    mapping: CalendarEventMapping | None
    source_attribution: str | None = None
    operator_notice: OperatorNotice | None = None


class SynchronizationQueryRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def get_by_event_id(
        self,
        event_id: int,
        calendar_id: str,
    ) -> SynchronizationEvent | None:
        with self._connect() as connection:
            return self._get_by_event_id(
                connection=connection,
                event_id=event_id,
                calendar_id=calendar_id,
            )

    def get_candidates(
        self,
        calendar_id: str,
        limit: int,
    ) -> list[SynchronizationEvent]:
        if limit <= 0:
            raise ValueError("Synchronization candidate limit must be positive.")

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT se.id
                FROM sports_events AS se
                LEFT JOIN calendar_event_mappings AS cem
                    ON cem.event_id = se.id
                   AND cem.calendar_id = ?
                WHERE (
                    cem.id IS NULL
                    AND se.deleted_at IS NULL
                )
                OR cem.sync_status IN (
                    'pending',
                    'failed',
                    'synced',
                    'delete_pending'
                )
                OR (
                    cem.sync_status = 'deleted'
                    AND se.deleted_at IS NULL
                )
                ORDER BY
                    CASE
                        WHEN cem.id IS NULL THEN 0
                        WHEN cem.sync_status != 'synced' THEN 0
                        WHEN se.sync_revision > cem.last_synced_revision THEN 0
                        WHEN EXISTS (
                            SELECT 1
                            FROM calendar_event_asset_attachments AS ceaa
                            WHERE ceaa.calendar_event_mapping_id = cem.id
                              AND ceaa.status != 'synced'
                        ) THEN 1
                        WHEN cem.presentation_revision >
                            cem.last_synced_presentation_revision THEN 1
                        ELSE 2
                    END,
                    CASE
                        WHEN cem.sync_status = 'synced'
                        THEN cem.last_synced_at
                    END,
                    se.start_time,
                    se.id
                LIMIT ?
                """,
                (
                    calendar_id,
                    limit,
                ),
            ).fetchall()

            candidates: list[SynchronizationEvent] = []

            for row in rows:
                candidate = self._get_by_event_id(
                    connection=connection,
                    event_id=row["id"],
                    calendar_id=calendar_id,
                )

                if candidate is None:
                    raise RuntimeError(
                        "Synchronization candidate disappeared while loading: "
                        f"event_id={row['id']}"
                    )

                candidates.append(candidate)

        return candidates

    def _get_by_event_id(
        self,
        connection: sqlite3.Connection,
        event_id: int,
        calendar_id: str,
    ) -> SynchronizationEvent | None:
        event_row = connection.execute(
            """
            SELECT *
            FROM sports_events
            WHERE id = ?
            """,
            (event_id,),
        ).fetchone()

        if event_row is None:
            return None

        event = self._map_sports_event(event_row)

        sport_row = connection.execute(
            """
            SELECT *
            FROM sports
            WHERE id = ?
            """,
            (event.sport_id,),
        ).fetchone()

        if sport_row is None:
            raise RuntimeError(f"Sport missing for sports event: event_id={event.id}")

        competition = self._load_competition(
            connection=connection,
            competition_id=event.competition_id,
        )
        season = self._load_season(
            connection=connection,
            season_id=event.season_id,
        )
        parent_event = self._load_parent_event(
            connection=connection,
            parent_event_id=event.parent_event_id,
        )
        participants = self._load_participants(
            connection=connection,
            event_id=event.id,
        )
        results = self._load_results(
            connection=connection,
            event_id=event.id,
        )
        statistics = self._load_statistics(
            connection=connection,
            event_id=event.id,
        )
        mapping = self._load_mapping(
            connection=connection,
            event_id=event.id,
            calendar_id=calendar_id,
        )
        source_attribution = self._load_source_attribution(
            connection=connection,
            competition_id=event.competition_id,
            season_id=event.season_id,
            stage=event.stage,
        )
        operator_notice = self._load_operator_notice(event.metadata)

        return SynchronizationEvent(
            event=event,
            sport=self._map_sport(sport_row),
            competition=competition,
            season=season,
            parent_event=parent_event,
            participants=participants,
            results=results,
            statistics=statistics,
            mapping=mapping,
            source_attribution=source_attribution,
            operator_notice=operator_notice,
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _load_competition(
        self,
        connection: sqlite3.Connection,
        competition_id: int | None,
    ) -> Competition | None:
        if competition_id is None:
            return None

        row = connection.execute(
            """
            SELECT *
            FROM competitions
            WHERE id = ?
            """,
            (competition_id,),
        ).fetchone()

        if row is None:
            raise RuntimeError(
                f"Competition missing for sports event: competition_id={competition_id}"
            )

        return self._map_competition(row)

    def _load_season(
        self,
        connection: sqlite3.Connection,
        season_id: int | None,
    ) -> Season | None:
        if season_id is None:
            return None

        row = connection.execute(
            """
            SELECT *
            FROM seasons
            WHERE id = ?
            """,
            (season_id,),
        ).fetchone()

        if row is None:
            raise RuntimeError(
                f"Season missing for sports event: season_id={season_id}"
            )

        return self._map_season(row)

    def _load_parent_event(
        self,
        connection: sqlite3.Connection,
        parent_event_id: int | None,
    ) -> SportsEvent | None:
        if parent_event_id is None:
            return None

        row = connection.execute(
            """
            SELECT *
            FROM sports_events
            WHERE id = ?
            """,
            (parent_event_id,),
        ).fetchone()

        if row is None:
            raise RuntimeError(
                "Parent event missing for sports event: "
                f"parent_event_id={parent_event_id}"
            )

        return self._map_sports_event(row)

    def _load_participants(
        self,
        connection: sqlite3.Connection,
        event_id: int,
    ) -> tuple[SynchronizationParticipant, ...]:
        rows = connection.execute(
            """
            SELECT
                p.*,
                ep.role AS event_role,
                ep.position_number AS event_position_number,
                ep.is_primary AS event_is_primary,
                ep.metadata_json AS event_metadata_json
            FROM event_participants AS ep
            INNER JOIN participants AS p
                ON p.id = ep.participant_id
            WHERE ep.event_id = ?
            ORDER BY
                ep.position_number IS NULL,
                ep.position_number,
                ep.id
            """,
            (event_id,),
        ).fetchall()

        return tuple(
            SynchronizationParticipant(
                participant=self._map_participant(row),
                role=row["event_role"],
                position_number=row["event_position_number"],
                is_primary=bool(row["event_is_primary"]),
                metadata=self._deserialize_metadata(
                    row["event_metadata_json"],
                ),
            )
            for row in rows
        )

    def _load_results(
        self,
        connection: sqlite3.Connection,
        event_id: int,
    ) -> tuple[EventResult, ...]:
        rows = connection.execute(
            """
            SELECT *
            FROM event_results
            WHERE event_id = ?
            ORDER BY
                position_number IS NULL,
                position_number,
                id
            """,
            (event_id,),
        ).fetchall()

        return tuple(self._map_event_result(row) for row in rows)

    def _load_statistics(
        self,
        connection: sqlite3.Connection,
        event_id: int,
    ) -> tuple[EventStatistic, ...]:
        rows = connection.execute(
            """
            SELECT *
            FROM event_statistics
            WHERE event_id = ?
            ORDER BY
                participant_id IS NULL,
                participant_id,
                statistic_key,
                recorded_at IS NULL,
                recorded_at,
                id
            """,
            (event_id,),
        ).fetchall()

        return tuple(self._map_event_statistic(row) for row in rows)

    def _load_mapping(
        self,
        connection: sqlite3.Connection,
        event_id: int,
        calendar_id: str,
    ) -> CalendarEventMapping | None:
        row = connection.execute(
            """
            SELECT *
            FROM calendar_event_mappings
            WHERE event_id = ?
              AND calendar_id = ?
            """,
            (
                event_id,
                calendar_id,
            ),
        ).fetchone()

        return None if row is None else self._map_calendar_event_mapping(row)

    def _load_source_attribution(
        self,
        connection: sqlite3.Connection,
        competition_id: int | None,
        season_id: int | None,
        stage: str | None = None,
    ) -> str | None:
        if competition_id is None or season_id is None:
            return None

        rows = connection.execute(
            """
            SELECT ds.metadata_json, sa.namespace, mp.attribution AS manual_attribution
            FROM source_assignments AS sa
            INNER JOIN data_sources AS ds
                ON ds.id = sa.source_id
            LEFT JOIN manual_import_profiles AS mp ON mp.namespace = sa.namespace
            WHERE sa.competition_id = ?
              AND sa.season_id = ?
              AND sa.role = 'authoritative'
              AND sa.is_enabled = 1
              AND ds.is_active = 1
              AND (sa.stages_json IS NULL OR ? IN
                   (SELECT value FROM json_each(sa.stages_json)))
            ORDER BY sa.id
            """,
            (competition_id, season_id, stage),
        ).fetchall()

        if not rows:
            return None
        if len(rows) > 1:
            raise RuntimeError(
                "Multiple active authoritative sources found for event scope."
            )

        if rows[0]["namespace"] is not None:
            return rows[0]["manual_attribution"]
        metadata = self._deserialize_metadata(rows[0]["metadata_json"])
        if metadata is None or "attribution" not in metadata:
            return None

        attribution = metadata["attribution"]
        if not isinstance(attribution, str):
            raise RuntimeError("Authoritative source attribution must be text.")

        return attribution.strip() or None

    @staticmethod
    def _load_operator_notice(
        metadata: dict[str, Any] | None,
    ) -> OperatorNotice | None:
        if metadata is None or OPERATOR_NOTICE_METADATA_KEY not in metadata:
            return None
        notice = metadata[OPERATOR_NOTICE_METADATA_KEY]
        if not isinstance(notice, str):
            raise RuntimeError("Canonical operator notice must be text.")
        try:
            return OperatorNotice(notice)
        except (TypeError, ValueError) as error:
            raise RuntimeError("Canonical operator notice is invalid.") from error

    @classmethod
    def _map_sports_event(
        cls,
        row: sqlite3.Row,
    ) -> SportsEvent:
        return SportsEvent(**cls._row_values(row))

    @classmethod
    def _map_sport(
        cls,
        row: sqlite3.Row,
    ) -> Sport:
        return Sport(**cls._row_values(row))

    @classmethod
    def _map_competition(
        cls,
        row: sqlite3.Row,
    ) -> Competition:
        return Competition(**cls._row_values(row))

    @classmethod
    def _map_season(
        cls,
        row: sqlite3.Row,
    ) -> Season:
        values = cls._row_values(row)
        values["is_current"] = bool(values["is_current"])
        return Season(**values)

    @classmethod
    def _map_participant(
        cls,
        row: sqlite3.Row,
    ) -> Participant:
        participant_columns = (
            "id",
            "sport_id",
            "participant_key",
            "participant_type",
            "name",
            "short_name",
            "country_code",
            "metadata_json",
            "created_at",
            "updated_at",
        )
        values = cls._row_values(row, participant_columns)
        return Participant(**values)

    @classmethod
    def _map_event_result(
        cls,
        row: sqlite3.Row,
    ) -> EventResult:
        values = cls._row_values(row)
        values["is_final"] = bool(values["is_final"])
        return EventResult(**values)

    @classmethod
    def _map_event_statistic(
        cls,
        row: sqlite3.Row,
    ) -> EventStatistic:
        return EventStatistic(**cls._row_values(row))

    @staticmethod
    def _map_calendar_event_mapping(
        row: sqlite3.Row,
    ) -> CalendarEventMapping:
        return CalendarEventMapping(**dict(row))

    @classmethod
    def _row_values(
        cls,
        row: sqlite3.Row,
        columns: tuple[str, ...] | None = None,
    ) -> dict[str, Any]:
        if columns is None:
            values = dict(row)
        else:
            values = {column: row[column] for column in columns}

        if "metadata_json" in values:
            metadata_json = values.pop("metadata_json")
            values["metadata"] = cls._deserialize_metadata(metadata_json)

        return values

    @staticmethod
    def _deserialize_metadata(
        metadata_json: str | None,
    ) -> dict[str, Any] | None:
        if metadata_json is None:
            return None

        return json.loads(metadata_json)
