import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SportsEvent:
    id: int
    sport_id: int
    competition_id: int | None
    season_id: int | None
    parent_event_id: int | None
    event_key: str
    event_type: str
    title: str
    stage: str | None
    round_name: str | None
    sequence_number: int | None
    start_time: str
    end_time: str | None
    timezone: str
    venue_name: str | None
    city: str | None
    country_code: str | None
    status: str
    source_updated_at: str | None
    first_seen_at: str
    last_seen_at: str
    cancelled_at: str | None
    deleted_at: str | None
    metadata: dict[str, Any] | None
    created_at: str
    updated_at: str


class SportsEventsRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def get_by_key(self, event_key: str) -> SportsEvent | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    sport_id,
                    competition_id,
                    season_id,
                    parent_event_id,
                    event_key,
                    event_type,
                    title,
                    stage,
                    round_name,
                    sequence_number,
                    start_time,
                    end_time,
                    timezone,
                    venue_name,
                    city,
                    country_code,
                    status,
                    source_updated_at,
                    first_seen_at,
                    last_seen_at,
                    cancelled_at,
                    deleted_at,
                    metadata_json,
                    created_at,
                    updated_at
                FROM sports_events
                WHERE event_key = ?
                """,
                (event_key,),
            ).fetchone()

        return None if row is None else self._map_row(row)

    def upsert(
        self,
        sport_id: int,
        event_key: str,
        event_type: str,
        title: str,
        start_time: str,
        competition_id: int | None = None,
        season_id: int | None = None,
        parent_event_id: int | None = None,
        stage: str | None = None,
        round_name: str | None = None,
        sequence_number: int | None = None,
        end_time: str | None = None,
        timezone: str = "UTC",
        venue_name: str | None = None,
        city: str | None = None,
        country_code: str | None = None,
        status: str = "scheduled",
        source_updated_at: str | None = None,
        cancelled_at: str | None = None,
        deleted_at: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SportsEvent:
        timestamp = datetime.now(UTC).isoformat()
        metadata_json = self._serialize_metadata(metadata)

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sports_events (
                    sport_id,
                    competition_id,
                    season_id,
                    parent_event_id,
                    event_key,
                    event_type,
                    title,
                    stage,
                    round_name,
                    sequence_number,
                    start_time,
                    end_time,
                    timezone,
                    venue_name,
                    city,
                    country_code,
                    status,
                    source_updated_at,
                    first_seen_at,
                    last_seen_at,
                    cancelled_at,
                    deleted_at,
                    metadata_json,
                    created_at,
                    updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?
                )
                ON CONFLICT (event_key)
                DO UPDATE SET
                    sport_id = excluded.sport_id,
                    competition_id = excluded.competition_id,
                    season_id = excluded.season_id,
                    parent_event_id = excluded.parent_event_id,
                    event_type = excluded.event_type,
                    title = excluded.title,
                    stage = excluded.stage,
                    round_name = excluded.round_name,
                    sequence_number = excluded.sequence_number,
                    start_time = excluded.start_time,
                    end_time = excluded.end_time,
                    timezone = excluded.timezone,
                    venue_name = excluded.venue_name,
                    city = excluded.city,
                    country_code = excluded.country_code,
                    status = excluded.status,
                    source_updated_at = excluded.source_updated_at,
                    last_seen_at = excluded.last_seen_at,
                    cancelled_at = excluded.cancelled_at,
                    deleted_at = excluded.deleted_at,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    sport_id,
                    competition_id,
                    season_id,
                    parent_event_id,
                    event_key,
                    event_type,
                    title,
                    stage,
                    round_name,
                    sequence_number,
                    start_time,
                    end_time,
                    timezone,
                    venue_name,
                    city,
                    country_code,
                    status,
                    source_updated_at,
                    timestamp,
                    timestamp,
                    cancelled_at,
                    deleted_at,
                    metadata_json,
                    timestamp,
                    timestamp,
                ),
            )

        event = self.get_by_key(event_key)

        if event is None:
            raise RuntimeError(
                f"Sports event could not be loaded after upsert: {event_key}"
            )

        return event

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _serialize_metadata(
        metadata: dict[str, Any] | None,
    ) -> str | None:
        if metadata is None:
            return None

        return json.dumps(
            metadata,
            ensure_ascii=False,
            sort_keys=True,
        )

    @staticmethod
    def _map_row(row: sqlite3.Row) -> SportsEvent:
        metadata_json = row["metadata_json"]

        return SportsEvent(
            id=row["id"],
            sport_id=row["sport_id"],
            competition_id=row["competition_id"],
            season_id=row["season_id"],
            parent_event_id=row["parent_event_id"],
            event_key=row["event_key"],
            event_type=row["event_type"],
            title=row["title"],
            stage=row["stage"],
            round_name=row["round_name"],
            sequence_number=row["sequence_number"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            timezone=row["timezone"],
            venue_name=row["venue_name"],
            city=row["city"],
            country_code=row["country_code"],
            status=row["status"],
            source_updated_at=row["source_updated_at"],
            first_seen_at=row["first_seen_at"],
            last_seen_at=row["last_seen_at"],
            cancelled_at=row["cancelled_at"],
            deleted_at=row["deleted_at"],
            metadata=(json.loads(metadata_json) if metadata_json is not None else None),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
