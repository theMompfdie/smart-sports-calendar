"""Read one consistent manual-preview snapshot without bootstrap or mutations."""

import hashlib
import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.imports.manual_manifest import ManualManifest, ManualReviewPlan, _review_plan


@dataclass(frozen=True)
class ManualPreviewState:
    database_ref: str
    catalog: dict[str, Any]
    participants: tuple[dict[str, Any], ...]
    events: tuple[dict[str, Any], ...]
    event_participants: tuple[dict[str, Any], ...]
    mappings: tuple[dict[str, Any], ...]
    assignments: tuple[dict[str, Any], ...]
    sources: tuple[dict[str, Any], ...]
    schema_versions: tuple[str, ...]
    accepted_review_plan: ManualReviewPlan | None = None
    configured_profile: dict[str, Any] | None = None
    instance_ref: str | None = None


class ManualPreviewRepository:
    """Only SELECTs on a mode=ro connection; never initialize missing databases."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def read(self, manifest: ManualManifest) -> ManualPreviewState:
        path = self.database_path.resolve(strict=True)
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only = ON")
            conn.execute("BEGIN")
            return self.read_connection(conn, manifest, str(path))

    @staticmethod
    def read_connection(
        conn: sqlite3.Connection, manifest: ManualManifest, database_identity: str
    ) -> ManualPreviewState:
        """Also usable inside the future apply transaction; performs only reads."""

        def rows(
            sql: str, params: tuple[object, ...] = ()
        ) -> tuple[dict[str, Any], ...]:
            return tuple(dict(row) for row in conn.execute(sql, params).fetchall())

        catalog = rows(
            """
            SELECT sport.id AS sport_id, competition.id AS competition_id,
                   season.id AS season_id, competition.competition_type,
                   season.start_date, season.end_date
            FROM sports AS sport
            JOIN competitions AS competition ON competition.sport_id = sport.id
            JOIN seasons AS season ON season.competition_id = competition.id
            WHERE sport.sport_key = ? AND competition.competition_key = ?
              AND season.season_key = ?
            """,
            (
                manifest.scope.sport_key,
                manifest.scope.competition_key,
                manifest.scope.season_key,
            ),
        )
        if len(catalog) != 1:
            raise ValueError("Catalog scope does not resolve to one season.")
        scope = catalog[0]
        prefix = manifest.namespace + ":"
        # Include namespace collisions outside the proposed season and absence
        # of new mappings, not merely existing mapped event revisions.
        mappings = rows(
            """
            SELECT m.source_id, m.external_id, m.internal_id
            FROM source_mappings AS m
            JOIN data_sources AS s ON s.id = m.source_id
            WHERE m.object_type = 'event' AND (
                (s.source_key = 'manual' AND substr(m.external_id, 1, ?) = ?)
                OR m.internal_id IN (
                    SELECT id FROM sports_events
                    WHERE competition_id = ? AND season_id = ?
                )
            ) ORDER BY m.source_id, m.external_id
            """,
            (len(prefix), prefix, scope["competition_id"], scope["season_id"]),
        )
        events = rows(
            """
            SELECT * FROM sports_events WHERE (competition_id = ? AND season_id = ?)
                OR substr(event_key, 1, ?) = ?
                OR id IN (
                    SELECT m.internal_id FROM source_mappings AS m
                    JOIN data_sources AS s ON s.id = m.source_id
                    WHERE m.object_type = 'event' AND s.source_key = 'manual'
                      AND substr(m.external_id, 1, ?) = ?
                ) ORDER BY id
            """,
            (
                scope["competition_id"],
                scope["season_id"],
                len("manual:fixture:" + prefix),
                "manual:fixture:" + prefix,
                len(prefix),
                prefix,
            ),
        )
        # Participant membership and display names influence both validation
        # and normalized titles. Changes invalidate the reviewed snapshot.
        participants = rows(
            """
            SELECT p.id, p.sport_id, p.participant_key, p.name
            FROM participants AS p JOIN season_participants AS sp
              ON sp.participant_id = p.id
            WHERE sp.season_id = ? ORDER BY p.id
            """,
            (scope["season_id"],),
        )
        event_participants = tuple(
            row
            for event in events
            for row in rows(
                """SELECT event_id, participant_id, role, position_number
                   FROM event_participants WHERE event_id = ?
                   ORDER BY position_number, participant_id, role""",
                (event["id"],),
            )
        )
        assignments = rows(
            """SELECT job_key, source_id, role, is_enabled, interval_seconds,
                      namespace, stages_json
               FROM source_assignments WHERE competition_id = ? AND season_id = ?
               ORDER BY job_key""",
            (scope["competition_id"], scope["season_id"]),
        )
        sources = rows(
            """SELECT id, source_key, is_active FROM data_sources
               WHERE source_key = 'manual' OR id IN (
                   SELECT source_id FROM source_assignments
                   WHERE competition_id = ? AND season_id = ?
               ) ORDER BY id""",
            (scope["competition_id"], scope["season_id"]),
        )
        versions = rows("SELECT version FROM schema_migrations ORDER BY version")
        instance = rows(
            "SELECT instance_id,instance_ref FROM manual_import_instance WHERE id=1"
        )
        if len(instance) != 1:
            raise ValueError("Durable database identity is missing.")
        profile = rows(
            """SELECT configuration_json,attribution FROM manual_import_profiles
                         WHERE namespace=?""",
            (manifest.namespace,),
        )
        review = rows(
            "SELECT plan_json FROM manual_review_plans WHERE namespace=?",
            (manifest.namespace,),
        )
        return ManualPreviewState(
            hashlib.sha256(
                (database_identity + ":" + instance[0]["instance_id"]).encode("utf-8")
            ).hexdigest(),
            scope,
            participants,
            events,
            event_participants,
            mappings,
            assignments,
            sources,
            tuple(row["version"] for row in versions),
            None if not review else _review_plan(json.loads(review[0]["plan_json"])),
            None if not profile else profile[0],
            instance[0]["instance_ref"],
        )
