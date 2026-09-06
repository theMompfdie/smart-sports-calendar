"""Project accepted update-review tasks without touching sports event mappings."""

import hashlib
import json
import logging
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from app.database.manual_review_repository import ManualReviewRepository
from app.graph.client import GraphClient, GraphClientError, OutlookEventNotFoundError
from app.imports.manual_inbox import encoded
from app.synchronization.outlook_event_payload_builder import (
    OutlookDateTime,
    OutlookEventPayload,
)


class ManualReviewService:
    def __init__(
        self,
        repository: ManualReviewRepository,
        graph: GraphClient,
        calendar: str,
        logger: logging.Logger,
        clock: Callable[[], datetime] | None = None,
    ):
        self.repository = repository
        self.graph = graph
        self.calendar = calendar
        self.logger = logger
        self.clock = clock or (lambda: datetime.now(UTC))
        self._cursor = ""

    def synchronize(self, limit: int = 10) -> None:
        if limit <= 0:
            raise ValueError("Reminder limit must be positive.")
        identity, plans, rows = self.repository.snapshot(self.calendar)
        existing = {(row["namespace"], row["task_id"]): row for row in rows}
        desired = []
        active = set()
        now = self.clock()
        if now.tzinfo is None:
            raise ValueError("Review clock must be timezone-aware.")
        for plan in plans:
            for task in json.loads(plan["plan_json"])["tasks"]:
                key = (plan["namespace"], task["task_id"])
                active.add(key)
                old = existing.get(key)
                task_json = encoded(task).decode()
                if old and not old["retired"] and old["task_json"] == task_json:
                    desired.append(old)
                    continue
                due = datetime.fromisoformat(task["due_at"])
                # Retain the first projection across note/round-only corrections.
                if (
                    old
                    and not old["retired"]
                    and json.loads(old["task_json"])["due_at"] == task["due_at"]
                ):
                    start = old["projected_start"]
                else:
                    start = (
                        max(due, now + timedelta(minutes=task["reminder_minutes"] + 5))
                        if due <= now
                        else due
                    ).isoformat()
                generation = old["generation"] if old else 1
                if old and old["retired"] and old["event_id"] is None:
                    generation += 1
                row = {
                    "namespace": key[0],
                    "task_id": key[1],
                    "calendar_id": self.calendar,
                    "task_json": task_json,
                    "projected_start": start,
                    "generation": generation,
                    "retired": 0,
                    "event_id": old["event_id"] if old else None,
                    "applied_hash": old["applied_hash"] if old else None,
                    "transaction_id": str(
                        uuid5(
                            NAMESPACE_URL,
                            encoded(
                                [identity, self.calendar, *key, generation]
                            ).decode(),
                        )
                    ),
                }
                row["desired_hash"] = hashlib.sha256(
                    encoded([task, start, generation])
                ).hexdigest()
                desired.append(row)
        for key, old in existing.items():
            if key not in active:
                desired.append({**old, "retired": 1, "desired_hash": "retired"})
        # Save intent and stable transaction IDs before any Graph call.
        changed = [
            row
            for row in desired
            if row != existing.get((row["namespace"], row["task_id"]))
        ]
        if changed:
            self.repository.desired(changed)
        pending = sorted(
            (row for row in desired if row["desired_hash"] != row["applied_hash"]),
            key=lambda row: row["namespace"] + ":" + row["task_id"],
        )
        pending = [r for r in pending if self._key(r) > self._cursor] + [
            r for r in pending if self._key(r) <= self._cursor
        ]
        for row in pending[:limit]:
            self._cursor = self._key(row)
            try:
                self._apply(row)
            except GraphClientError:
                self.logger.warning(
                    "Manual review appointment pending: namespace=%s task=%s",
                    row["namespace"],
                    row["task_id"],
                )

    @staticmethod
    def _key(row: dict) -> str:
        return row["namespace"] + ":" + row["task_id"]

    @staticmethod
    def payload(row: dict) -> OutlookEventPayload:
        task = json.loads(row["task_json"])
        start = datetime.fromisoformat(row["projected_start"])

        def local(value: datetime) -> OutlookDateTime:
            return OutlookDateTime(
                value.astimezone(ZoneInfo("Europe/Vienna"))
                .replace(tzinfo=None)
                .isoformat(),
                "W. Europe Standard Time",
            )

        body = (
            "Manual fixture update required. Review the source, "
            "prepare a new manifest, "
            "preview and explicitly approve it.\n"
            f"Namespace: {row['namespace']}\nReason: {task['reason']}\n"
            f"Original due time (UTC): {task['due_at']}\n"
            f"Stage: {task['target_stage'] or '-'}; "
            f"round: {task['target_round'] or '-'}\n"
            f"{task['note'] or ''}"
        )
        return OutlookEventPayload(
            subject=f"[Manual update] {row['namespace']} - {task['reason']}",
            body=body,
            start=local(start),
            end=local(start + timedelta(minutes=15)),
            location=None,
            categories=("SMART Manual Updates",),
            is_all_day=False,
            is_reminder_on=True,
            reminder_minutes_before_start=task["reminder_minutes"],
            show_as="free",
            body_content_type="text",
        )

    def _apply(self, row: dict) -> None:
        event_id = row["event_id"]
        if row["retired"]:
            if event_id is None and row["applied_hash"] is None:
                # Recover a possibly committed POST before retiring its intent.
                event_id = self.graph.create_event(
                    self.calendar, self.payload(row), row["transaction_id"]
                ).id
            if event_id:
                with suppress(OutlookEventNotFoundError):
                    self.graph.delete_event(self.calendar, event_id)
            self.repository.completed(row, None)
        elif event_id:
            try:
                result = self.graph.update_event(
                    self.calendar, event_id, self.payload(row)
                )
                self.repository.completed(row, result.id)
            except OutlookEventNotFoundError:
                # A deleted event requires a fresh creation identity, persisted first.
                row = {
                    **row,
                    "event_id": None,
                    "generation": row["generation"] + 1,
                    "applied_hash": None,
                    "transaction_id": str(
                        uuid5(NAMESPACE_URL, row["transaction_id"] + ":recreate")
                    ),
                }
                self.repository.desired([row])
        else:
            result = self.graph.create_event(
                self.calendar, self.payload(row), row["transaction_id"]
            )
            self.graph.update_event(self.calendar, result.id, self.payload(row))
            self.repository.completed(row, result.id)
