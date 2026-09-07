"""Durable retirement gates; authority and historical attribution stay intact."""

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

# Match an event alias `se` against the unchanged retired authority boundary.
RETIRED_EVENT_SQL = """
            EXISTS ( SELECT 1 FROM scope_retirements r JOIN source_assignments a ON
            a.job_key=r.job_key WHERE r.reactivated_at IS NULL AND
            a.competition_id=se.competition_id AND a.season_id=se.season_id AND
            (a.stages_json IS NULL OR se.stage IN (SELECT value FROM
            json_each(a.stages_json))))
            """


class ScopeRetirementRepository:
    def __init__(self, path: Path) -> None:
        self.path = path

    @contextmanager
    def transaction(self) -> Iterator["ScopeRetirementTransaction"]:
        with (
            closing(
                sqlite3.connect(
                    self.path.resolve(strict=True).as_uri() + "?mode=rw", uri=True
                )
            ) as conn,
            conn,
        ):
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("BEGIN IMMEDIATE")
            yield ScopeRetirementTransaction(conn)

    @staticmethod
    def blocked_connection(conn: sqlite3.Connection, job_key: str) -> bool:
        return (
            conn.execute(
                """
            SELECT 1 FROM source_assignments candidate JOIN source_assignments
            retired ON retired.competition_id=candidate.competition_id AND
            retired.season_id=candidate.season_id JOIN scope_retirements r ON
            r.job_key=retired.job_key WHERE candidate.job_key=? AND r.reactivated_at
            IS NULL AND (candidate.stages_json IS NULL OR retired.stages_json IS
            NULL OR EXISTS (SELECT 1 FROM json_each(candidate.stages_json) c JOIN
            json_each(retired.stages_json) s ON c.value=s.value)) LIMIT 1
            """,
                (job_key,),
            ).fetchone()
            is not None
        )

    def blocked(self, job_key: str) -> bool:
        with self.transaction() as conn:
            return self.blocked_connection(conn._connection, job_key)

    @staticmethod
    def require_manual_active(conn: sqlite3.Connection, namespace: str) -> None:
        if ScopeRetirementRepository.blocked_connection(conn, "manual:" + namespace):
            raise ValueError("Competition scope is retired; reactivate explicitly.")


class ScopeRetirementTransaction:
    """Persistence operations inside the caller-owned retirement transaction."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def assignment(self, job_key: str) -> sqlite3.Row | None:
        return self._connection.execute(
            "SELECT * FROM source_assignments WHERE job_key=?", (job_key,)
        ).fetchone()

    def retirement(self, job_key: str) -> sqlite3.Row | None:
        return self._connection.execute(
            "SELECT * FROM scope_retirements WHERE job_key=?", (job_key,)
        ).fetchone()

    def assignments(self, competition_id: int, season_id: int) -> list[sqlite3.Row]:
        return list(
            self._connection.execute(
                """
            SELECT * FROM source_assignments WHERE competition_id=? AND season_id=?
            AND is_enabled=1 ORDER BY job_key
            """,
                (competition_id, season_id),
            )
        )

    def events(self, competition_id: int, season_id: int) -> list[sqlite3.Row]:
        return list(
            self._connection.execute(
                """
            SELECT * FROM sports_events WHERE competition_id=? AND season_id=? ORDER
            BY id
            """,
                (competition_id, season_id),
            )
        )

    def mapping(self, event_id: int, calendar_id: str) -> sqlite3.Row | None:
        return self._connection.execute(
            "SELECT * FROM calendar_event_mappings WHERE event_id=? AND calendar_id=?",
            (event_id, calendar_id),
        ).fetchone()

    def pending_media(self, mapping_id: int) -> sqlite3.Row | None:
        return self._connection.execute(
            """
            SELECT 1 FROM calendar_event_asset_attachments WHERE
            calendar_event_mapping_id=? AND status!='synced'
            """,
            (mapping_id,),
        ).fetchone()

    def pending_batches(self, namespace: str) -> list[sqlite3.Row]:
        return list(
            self._connection.execute(
                """
            SELECT submission_id,state FROM import_batches WHERE namespace=? AND
            state NOT IN ('APPLIED','REJECTED') ORDER BY submission_id
            """,
                (namespace,),
            )
        )

    def review_plan(self, namespace: str) -> sqlite3.Row | None:
        return self._connection.execute(
            "SELECT plan_json FROM manual_review_plans WHERE namespace=?", (namespace,)
        ).fetchone()

    def review_appointments(self, namespace: str) -> list[sqlite3.Row]:
        return list(
            self._connection.execute(
                """
            SELECT namespace,task_id,
            calendar_id,event_id,desired_hash,applied_hash,retired FROM
            manual_review_appointments WHERE namespace=? ORDER BY
            calendar_id,task_id
            """,
                (namespace,),
            )
        )

    def observations(self, namespace: str) -> list[sqlite3.Row]:
        return list(
            self._connection.execute(
                """
            SELECT b.payload FROM import_batches b JOIN manual_import_receipts r
            USING(submission_id) WHERE b.namespace=? ORDER BY r.committed_at,r.rowid
            """,
                (namespace,),
            )
        )

    def database_identity(self) -> sqlite3.Row | None:
        return self._connection.execute(
            "SELECT instance_id FROM manual_import_instance WHERE id=1", ()
        ).fetchone()

    def saved_decision(self, job_key: str) -> sqlite3.Row | None:
        return self._connection.execute(
            "SELECT decision_json FROM scope_retirements WHERE job_key=?", (job_key,)
        ).fetchone()

    def deactivate(
        self, job_key: str, decision_json: str, timestamp: str
    ) -> sqlite3.Cursor:
        return self._connection.execute(
            """
            INSERT INTO scope_retirements(job_key,decision_json,retired_at) VALUES
            (?,?,?) ON CONFLICT(job_key) DO UPDATE SET
            decision_json=excluded.decision_json,retired_at=excluded.retired_at,
            reactivated_at=NULL
            """,
            (job_key, decision_json, timestamp),
        )

    def reject_batches(self, timestamp: str, namespace: str) -> sqlite3.Cursor:
        return self._connection.execute(
            """
            UPDATE import_batches SET state='REJECTED',
            approval_payload=NULL,error_code='scope_retired',updated_at=? WHERE
            namespace=? AND state NOT IN ('APPLIED','REJECTED')
            """,
            (timestamp, namespace),
        )

    def complete_review_plan(
        self, plan_json: str, timestamp: str, namespace: str
    ) -> sqlite3.Cursor:
        return self._connection.execute(
            """
            UPDATE manual_review_plans SET plan_json=?,updated_at=? WHERE
            namespace=?
            """,
            (plan_json, timestamp, namespace),
        )

    def reactivate(self, timestamp: str, job_key: str) -> sqlite3.Cursor:
        return self._connection.execute(
            "UPDATE scope_retirements SET reactivated_at=? WHERE job_key=?",
            (timestamp, job_key),
        )

    def audit_scope(self, job_key: str) -> sqlite3.Row | None:
        return self._connection.execute(
            "SELECT source_id,competition_id,season_id,namespace,stages_json "
            "FROM source_assignments WHERE job_key=?",
            (job_key,),
        ).fetchone()

    def append_audit(
        self, job_key: str, operation: str, decision_json: str, recorded_at: str
    ) -> None:
        self._connection.execute(
            "INSERT INTO scope_retirement_audit "
            "(job_key,operation,decision_json,recorded_at) VALUES (?,?,?,?)",
            (job_key, operation, decision_json, recorded_at),
        )

    def instance_ref(self) -> sqlite3.Row | None:
        return self._connection.execute(
            "SELECT instance_ref FROM manual_import_instance WHERE id=1"
        ).fetchone()
