"""Separate durable Outlook mappings for operator review appointments."""

import sqlite3
from contextlib import closing
from pathlib import Path

from app.database.scope_retirement_repository import ScopeRetirementRepository


class ManualReviewRepository:
    def __init__(self, path: Path):
        self.path = path

    def _connect(self):
        conn = sqlite3.connect(
            self.path.resolve(strict=True).as_uri() + "?mode=rw", uri=True
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def snapshot(self, calendar: str) -> tuple[str, list[dict], list[dict]]:
        with closing(self._connect()) as conn, conn:
            identity = conn.execute(
                "SELECT instance_id FROM manual_import_instance WHERE id=1"
            ).fetchone()[0]
            plans = [
                dict(row)
                for row in conn.execute("""SELECT p.namespace,p.plan_json
                FROM manual_review_plans AS p
                JOIN source_assignments AS a ON a.namespace=p.namespace
                JOIN data_sources AS s ON s.id=a.source_id
                WHERE a.is_enabled=1 AND a.role='authoritative' AND s.is_active=1""")
            ]
            rows = [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM manual_review_appointments WHERE calendar_id=?",
                    (calendar,),
                )
            ]
            # Exclude both sides of the projection: omitting only plans would
            # turn preserved appointments into deletion candidates.
            namespaces = {row["namespace"] for row in [*plans, *rows]}
            frozen = {
                namespace
                for namespace in namespaces
                if ScopeRetirementRepository.blocked_connection(
                    conn, "manual:" + namespace
                )
            }
            return (
                identity,
                [plan for plan in plans if plan["namespace"] not in frozen],
                [row for row in rows if row["namespace"] not in frozen],
            )

    def desired(self, rows: list[dict]) -> None:
        with closing(self._connect()) as conn, conn:
            for row in rows:
                conn.execute(
                    """INSERT INTO manual_review_appointments
                    (namespace,task_id,calendar_id,generation,task_json,projected_start,
                     desired_hash,applied_hash,event_id,transaction_id,retired)
                    VALUES (:namespace,:task_id,:calendar_id,:generation,
                     :task_json,:projected_start,
                     :desired_hash,:applied_hash,:event_id,
                     :transaction_id,:retired)
                    ON CONFLICT(namespace,task_id,calendar_id) DO UPDATE SET
                    generation=excluded.generation,
                    task_json=excluded.task_json,
                    projected_start=excluded.projected_start,desired_hash=excluded.desired_hash,
                    applied_hash=excluded.applied_hash,event_id=excluded.event_id,
                    transaction_id=excluded.transaction_id,retired=excluded.retired""",
                    row,
                )

    def completed(self, row: dict, event_id: str | None) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """UPDATE manual_review_appointments SET event_id=?,applied_hash=?
                WHERE namespace=? AND task_id=? AND calendar_id=? AND desired_hash=?""",
                (
                    event_id,
                    row["desired_hash"],
                    row["namespace"],
                    row["task_id"],
                    row["calendar_id"],
                    row["desired_hash"],
                ),
            )
