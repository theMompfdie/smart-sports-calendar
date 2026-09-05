"""Bounded scheduled transport processing; the owning process performs all writes."""

import hashlib
import json
import logging
import sqlite3
from threading import Lock

from app.application.manual_import_service import ManualImportService
from app.application.manual_preview_service import parse_preview_configuration
from app.imports.manual_files import read_bounded
from app.imports.manual_inbox import (
    MAX_TRANSPORT_BYTES,
    ManualInbox,
    atomic_write,
    encoded,
    identifier,
)
from app.imports.manual_manifest import parse_manifest


class ManualImportWorker:
    def __init__(
        self,
        inbox: ManualInbox,
        service: ManualImportService,
        logger: logging.Logger,
        limit: int = 10,
    ):
        if limit <= 0:
            raise ValueError("Worker limit must be positive.")
        self.inbox = inbox
        self.service = service
        self.logger = logger
        self.limit = limit
        self._lock = Lock()
        self._cursor = ""

    def initialize(self) -> None:
        self.inbox.initialize()
        with self.service.repository.transaction() as tx:
            row = tx.database_identity()
        atomic_write(self.inbox.root / "database.json", encoded(row), immutable=True)
        for path in sorted((self.inbox.root / "profiles").glob("*.json")):
            profile = parse_preview_configuration(read_bounded(path))
            if profile.instance_ref != self.inbox.instance:
                raise ValueError("Trusted profile belongs to another instance.")
            self.service.configure(profile)

    def run(self) -> None:
        if not self._lock.acquire(blocking=False):
            self.logger.warning("Manual inbox skipped: worker lock is held")
            return
        try:
            self.inbox.verify()
            paths = sorted((self.inbox.root / "pending").glob("*.json"))
            paths = [p for p in paths if p.name > self._cursor] + [
                p for p in paths if p.name <= self._cursor
            ]
            for path in paths[: self.limit]:
                self._cursor = path.name
                try:
                    self._process(path)
                except (OSError, sqlite3.Error, ValueError):
                    self.logger.warning("Manual inbox unavailable; retry next cycle")
        finally:
            self._lock.release()

    def _process(self, path) -> None:
        namespace = submission = None
        payload = read_bounded(path, limit=MAX_TRANSPORT_BYTES)
        try:
            if hashlib.sha256(payload).hexdigest() + ".json" != path.name:
                raise ValueError("Invalid transport fingerprint.")
            request = json.loads(payload)
            if not isinstance(request, dict) or set(request) != {
                "request_id",
                "action",
                "namespace",
                "submission_id",
                "instance",
                "payload",
            }:
                raise ValueError("Invalid request envelope.")
            if request["instance"] != self.inbox.instance:
                raise ValueError("Wrong instance.")
            namespace = identifier(request["namespace"])
            submission = identifier(request["submission_id"])
            if not isinstance(request["payload"], str):
                raise ValueError("Invalid payload.")
            action = request["action"]
            if action == "submit":
                manifest = parse_manifest(request["payload"].encode())
                if (
                    manifest.namespace != namespace
                    or manifest.submission_id != submission
                ):
                    raise ValueError("Wrong package scope.")
                state = self.service.receive(manifest.payload)
                if state == "RECEIVED":
                    self.service.prepare(submission)
            elif action in {"preview", "approve"}:
                with self.service.repository.transaction() as tx:
                    batch = tx.batch(submission)
                if batch["namespace"] != namespace:
                    raise ValueError("Wrong package scope.")
                if action == "preview":
                    self.service.prepare(submission)
                else:
                    self.service.approve(submission, request["payload"].encode())
                    self.service.apply(submission)
            else:
                raise ValueError("Unknown command.")
            self._publish(namespace, submission)
        except (ValueError, TypeError, KeyError):
            if namespace is not None and submission is not None:
                self._publish(
                    namespace, submission, error="validation_or_stale_approval"
                )
            self.logger.warning("Manual inbox request rejected; inspect private status")
        except sqlite3.Error:
            if namespace is not None and submission is not None:
                self._publish(
                    namespace, submission, error="persistence_retry", retry=True
                )
            raise
        # Publish before archiving. A crash replays the immutable request safely.
        atomic_write(self.inbox.root / "archive" / path.name, payload, immutable=True)
        path.unlink()

    def _publish(
        self,
        namespace: str,
        submission: str,
        error: str | None = None,
        retry: bool = False,
    ) -> None:
        result = {
            "namespace": namespace,
            "submission_id": submission,
            "state": "REJECTED",
            "error": error,
        }
        with self.service.repository.transaction() as tx:
            try:
                batch = tx.batch(submission)
            except ValueError:
                batch = None
            if batch is not None and batch["namespace"] == namespace:
                result["state"] = batch["state"]
                if batch["preview_json"]:
                    result["preview"] = json.loads(batch["preview_json"])
                    result["preview_sha256"] = batch["preview_sha256"]
                if batch["state"] == "APPLIED":
                    result["receipt"] = json.loads(tx.receipt(submission))
        if retry:
            result["state"] = "RETRYABLE_FAILURE"
        atomic_write(self.inbox.result_path(namespace, submission), encoded(result))
        self.logger.info(
            "Manual inbox operation completed: submission=%s state=%s",
            submission,
            result["state"],
        )
