"""Transaction-owned persistence for reviewed manual import packages."""

import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any

from app.database.fixture_import_repository import (
    FixtureImportRecord,
    FixtureImportRepository,
    FixtureImportScopeRecord,
)
from app.database.manual_preview_repository import ManualPreviewRepository
from app.database.source_assignments_repository import (
    SourceAssignmentsRepository,
    SourceAssignmentWrite,
)
from app.imports.manual_manifest import ManualManifest, ManualSourceProfile
from app.providers.contracts import SourceRole


class ManualImportRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    @contextmanager
    def transaction(self):
        path = self.database_path.resolve(strict=True)
        with closing(
            sqlite3.connect(path.as_uri() + "?mode=rw", uri=True)
        ) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield ManualImportTransaction(connection, path)
                connection.commit()
            except Exception:
                connection.rollback()
                raise


class ManualImportTransaction:
    def __init__(self, connection: sqlite3.Connection, path: Path) -> None:
        self._connection = connection
        self._path = path

    def batch(self, submission_id: str) -> dict[str, Any]:
        row = self._connection.execute(
            "SELECT * FROM import_batches WHERE submission_id=?", (submission_id,)
        ).fetchone()
        if row is None:
            raise ValueError("Import package is not staged.")
        return dict(row)

    def receive(self, manifest: ManualManifest, timestamp: str) -> str:
        row = self._connection.execute(
            "SELECT * FROM import_batches WHERE submission_id=?",
            (manifest.submission_id,),
        ).fetchone()
        if row is not None:
            if (
                row["payload"] != manifest.payload
                or row["manifest_sha256"] != manifest.fingerprint
            ):
                raise ValueError("Submission ID is already bound to different bytes.")
            return row["state"]
        self._connection.execute(
            """INSERT INTO import_batches
            (submission_id,namespace,import_type,schema_version,payload,manifest_sha256,
             state,created_at,updated_at) VALUES (?,?,?,?,?,?,'RECEIVED',?,?)""",
            (
                manifest.submission_id,
                manifest.namespace,
                manifest.import_type,
                manifest.schema_version,
                manifest.payload,
                manifest.fingerprint,
                timestamp,
                timestamp,
            ),
        )
        return "RECEIVED"

    def profile(self, namespace: str) -> bytes:
        row = self._connection.execute(
            """SELECT configuration_json
            FROM manual_import_profiles WHERE namespace=?""",
            (namespace,),
        ).fetchone()
        if row is None:
            raise ValueError("No trusted manual profile is registered.")
        return row["configuration_json"].encode("utf-8")

    def configure(
        self,
        profile: ManualSourceProfile,
        instance_ref: str,
        configuration_json: str,
        timestamp: str,
    ) -> None:
        conn = self._connection
        instance = conn.execute(
            "SELECT instance_ref FROM manual_import_instance WHERE id=1"
        ).fetchone()
        if instance is None or instance["instance_ref"] not in (None, instance_ref):
            raise ValueError("Manual profile belongs to another configured instance.")
        catalog = conn.execute(
            """SELECT c.id AS competition_id,s.id AS season_id,
            c.competition_type FROM sports AS sport
            JOIN competitions AS c ON c.sport_id=sport.id
            JOIN seasons AS s ON s.competition_id=c.id
            WHERE sport.sport_key=? AND c.competition_key=? AND s.season_key=?""",
            (
                profile.scope.sport_key,
                profile.scope.competition_key,
                profile.scope.season_key,
            ),
        ).fetchone()
        if (
            catalog is None
            or catalog["competition_type"] != profile.competition_format.value
        ):
            raise ValueError("Manual profile does not match the canonical catalog.")
        conn.execute(
            """INSERT INTO data_sources(source_key,name,created_at,updated_at)
            VALUES ('manual','Reviewed manual imports',?,?)
            ON CONFLICT(source_key) DO NOTHING""",
            (timestamp, timestamp),
        )
        source = conn.execute(
            "SELECT id,is_active FROM data_sources WHERE source_key='manual'"
        ).fetchone()
        if not source["is_active"]:
            raise ValueError("Manual source is inactive.")
        SourceAssignmentsRepository.write_connection(
            conn,
            SourceAssignmentWrite(
                job_key="manual:" + profile.namespace,
                source_id=source["id"],
                competition_id=catalog["competition_id"],
                season_id=catalog["season_id"],
                role=SourceRole.AUTHORITATIVE,
                interval_seconds=None,
                namespace=profile.namespace,
                stages=frozenset(boundary.stage for boundary in profile.boundaries),
            ),
            timestamp,
        )
        conn.execute(
            """UPDATE manual_import_instance SET instance_ref=?
            WHERE id=1 AND instance_ref IS NULL""",
            (instance_ref,),
        )
        conn.execute(
            """INSERT INTO manual_import_profiles
            (namespace,configuration_json,updated_at) VALUES (?,?,?)
            ON CONFLICT(namespace) DO UPDATE SET
            configuration_json=excluded.configuration_json,updated_at=excluded.updated_at
            WHERE manual_import_profiles.configuration_json
                IS NOT excluded.configuration_json""",
            (profile.namespace, configuration_json, timestamp),
        )

    def snapshot(self, manifest: ManualManifest):
        return ManualPreviewRepository.read_connection(
            self._connection, manifest, str(self._path)
        )

    def save_preview(
        self,
        submission_id: str,
        payload: str,
        fingerprint: str,
        accepted: bool,
        timestamp: str,
    ) -> None:
        self._connection.execute(
            """UPDATE import_batches
            SET state=?,preview_json=?,preview_sha256=?,approval_payload=NULL,
                error_code=?,updated_at=? WHERE submission_id=?""",
            (
                "AWAITING_APPROVAL" if accepted else "REJECTED",
                payload,
                fingerprint,
                None if accepted else "validation_failed",
                timestamp,
                submission_id,
            ),
        )

    def needs_review(self, submission_id: str, timestamp: str) -> None:
        self._connection.execute(
            """UPDATE import_batches SET state='NEEDS_REVIEW',
            approval_payload=NULL,error_code='stale_preconditions',updated_at=?
            WHERE submission_id=?""",
            (timestamp, submission_id),
        )

    def approve(self, submission_id: str, payload: bytes, timestamp: str) -> None:
        self._connection.execute(
            """UPDATE import_batches SET state='APPROVED',
            approval_payload=?,error_code=NULL,updated_at=? WHERE submission_id=?""",
            (payload, timestamp, submission_id),
        )

    def import_records(
        self,
        source_id: int,
        records: tuple[FixtureImportRecord, ...],
        scope: FixtureImportScopeRecord,
        namespace: str,
    ):
        return FixtureImportRepository(self._path).import_in_transaction(
            self._connection, source_id, records, scope, namespace=namespace
        )

    def receipt(self, submission_id: str) -> str:
        row = self._connection.execute(
            "SELECT receipt_json FROM manual_import_receipts WHERE submission_id=?",
            (submission_id,),
        ).fetchone()
        if row is None:
            raise ValueError("Applied package has no receipt.")
        return row["receipt_json"]

    def complete(
        self,
        manifest: ManualManifest,
        receipt_json: str,
        plan_json: str,
        timestamp: str,
    ) -> None:
        conn = self._connection
        conn.execute(
            """INSERT INTO manual_import_receipts
            (submission_id,receipt_json,committed_at) VALUES (?,?,?)""",
            (manifest.submission_id, receipt_json, timestamp),
        )
        conn.execute(
            """INSERT INTO manual_review_plans
            (namespace,submission_id,plan_json,updated_at) VALUES (?,?,?,?)
            ON CONFLICT(namespace) DO UPDATE SET submission_id=excluded.submission_id,
            plan_json=excluded.plan_json,updated_at=excluded.updated_at
            WHERE manual_review_plans.plan_json IS NOT excluded.plan_json""",
            (manifest.namespace, manifest.submission_id, plan_json, timestamp),
        )
        conn.execute(
            """UPDATE manual_import_profiles SET attribution=?,updated_at=?
            WHERE namespace=? AND attribution IS NOT ?""",
            (
                manifest.provenance.attribution,
                timestamp,
                manifest.namespace,
                manifest.provenance.attribution,
            ),
        )
        conn.execute(
            """UPDATE import_batches SET state='APPLIED',error_code=NULL,
            updated_at=? WHERE submission_id=?""",
            (timestamp, manifest.submission_id),
        )
