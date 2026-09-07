"""Operator-reviewed, single-owner retirement without fixture mutation."""

import hashlib
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.database.scope_retirement_repository import (
    ScopeRetirementRepository,
    ScopeRetirementTransaction,
)
from app.imports.manual_files import read_bounded
from app.imports.manual_inbox import MAX_TRANSPORT_BYTES, ManualInbox, identifier
from app.imports.manual_manifest import IDENTIFIER
from app.operations.instance_lock import instance_lock


def encoded(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class ScopeRetirementService:
    def __init__(
        self,
        repository: ScopeRetirementRepository,
        calendar: str,
        clock: Callable[[], datetime] | None = None,
        inbox_root: Path | None = None,
    ) -> None:
        if not calendar.strip():
            raise ValueError("The configured SMART calendar is required.")
        self.inbox_root = inbox_root
        self.repository = repository
        self.calendar = calendar
        self.clock = clock or (lambda: datetime.now(UTC))
        self.logger = logging.getLogger(__name__)

    def _now(self) -> datetime:
        now = self.clock()
        if now.tzinfo is None:
            raise ValueError("Retirement clock must be timezone-aware.")
        return now.astimezone(UTC)

    @staticmethod
    def _decision(decision: dict) -> datetime:
        if set(decision) != {
            "operator_ref",
            "evidence_ref",
            "completed_at",
            "grace_days",
            "complete_schedule_confirmed",
        }:
            raise ValueError("Invalid retirement decision fields.")
        for key in ("operator_ref", "evidence_ref"):
            if not isinstance(decision[key], str) or not IDENTIFIER.fullmatch(
                decision[key]
            ):
                raise ValueError(
                    "Use non-secret identifier references for evidence/operator."
                )
        if decision["complete_schedule_confirmed"] is not True:
            raise ValueError(
                "Explicit confirmation of the entire owned schedule is required."
            )
        days = decision["grace_days"]
        if type(days) is not int or not 0 <= days <= 3650:
            raise ValueError("grace_days must be an integer between 0 and 3650.")
        completed = datetime.fromisoformat(decision["completed_at"])
        if completed.tzinfo is None:
            raise ValueError("completed_at must be timezone-aware.")
        return completed

    def preview(self, job_key: str, decision: dict) -> dict:
        with instance_lock(self.repository.path), self.repository.transaction() as tx:
            return self._preview(tx, job_key, decision)

    def _preview(
        self, tx: ScopeRetirementTransaction, job_key: str, decision: dict
    ) -> dict:
        completed = self._decision(decision)
        assignment = tx.assignment(job_key)
        if assignment is None or assignment["role"] != "authoritative":
            raise ValueError(
                "Select an existing authoritative job, including its full grant."
            )
        a = dict(assignment)
        stages = None if a["stages_json"] is None else set(json.loads(a["stages_json"]))
        state = tx.retirement(job_key)
        inactive = state is not None and state["reactivated_at"] is None
        blockers = []
        if not a["is_enabled"]:
            blockers.append("authority_disabled")
        if self._now() < completed + timedelta(days=decision["grace_days"]):
            blockers.append("correction_grace_period_not_elapsed")
        jobs = []
        namespaces = []
        for row in tx.assignments(a["competition_id"], a["season_id"]):
            other = (
                None
                if row["stages_json"] is None
                else set(json.loads(row["stages_json"]))
            )
            if (
                stages is not None
                and other is not None
                and not stages.intersection(other)
            ):
                continue
            if stages is not None and (other is None or not other <= stages):
                blockers.append("overlapping_job_exceeds_boundary:" + row["job_key"])
            jobs.append(row["job_key"])
            if row["namespace"]:
                namespaces.append(row["namespace"])
        events = [
            dict(row)
            for row in tx.events(a["competition_id"], a["season_id"])
            if stages is None or row["stage"] in stages
        ]
        pending_graph = []
        unresolved = []
        for event in events:
            if (
                event["status"] in {"postponed", "suspended", "abandoned", "live"}
                or datetime.fromisoformat(event["end_time"] or event["start_time"])
                > completed
                or (
                    json.loads(event["metadata_json"] or "{}").get("operator_notice")
                    and event["status"] != "cancelled"
                )
            ):
                unresolved.append(event["id"])
            mapping = tx.mapping(event["id"], self.calendar)
            if mapping is None:
                pending = event["deleted_at"] is None
            else:
                terminal = "deleted" if event["deleted_at"] else "synced"
                pending = mapping["sync_status"] != terminal or (
                    terminal == "synced"
                    and (
                        mapping["last_synced_revision"] < event["sync_revision"]
                        or mapping["last_synced_presentation_revision"]
                        < mapping["presentation_revision"]
                        or tx.pending_media(mapping["id"]) is not None
                    )
                )
            if pending:
                pending_graph.append(event["id"])
        if unresolved:
            blockers.append("unresolved_or_later_fixtures")
        if pending_graph:
            blockers.append("pending_fixture_graph_work")
        batches, plans, appointments = [], [], []
        for namespace in namespaces:
            batches.extend(dict(r) for r in tx.pending_batches(namespace))
            plan = tx.review_plan(namespace)
            if plan:
                plans.append({"namespace": namespace, "plan": json.loads(plan[0])})
            appointments.extend(dict(r) for r in tx.review_appointments(namespace))
            # Deferred fixtures may have no canonical row. Inspect the latest accepted
            # observation per stable manual ID, including partial package corrections.
            fixtures = {}
            for row in tx.observations(namespace):
                for fixture in json.loads(row[0])["fixtures"]:
                    fixtures[fixture["fixture_id"]] = fixture
            if any(
                not f["kickoff_confirmed"]
                or f["home"]["resolution"] != "resolved"
                or f["away"]["resolution"] != "resolved"
                or f["status"] in {"postponed", "suspended", "abandoned", "live"}
                for f in fixtures.values()
            ):
                blockers.append("unresolved_manual_observations:" + namespace)
        if any(
            r["calendar_id"] != self.calendar
            and (r["event_id"] is not None or r["desired_hash"] != r["applied_hash"])
            for r in appointments
        ):
            blockers.append("review_work_in_another_calendar")
        pending_reviews = [
            r
            for r in appointments
            if r["event_id"] is not None or r["desired_hash"] != r["applied_hash"]
        ]
        transport = []
        if namespaces:
            if self.inbox_root is None:
                blockers.append("manual_inbox_required")
            else:
                try:
                    transport = self._transport(
                        namespaces, tx.instance_ref()[0], tx.database_identity()[0]
                    )
                except (OSError, ValueError, TypeError, KeyError):
                    blockers.append("manual_inbox_uninspectable")
        report = {
            "job_key": job_key,
            "calendar_id": self.calendar,
            "database_id": tx.database_identity()[0],
            "assignment": a,
            "decision": decision,
            "routine_jobs": jobs,
            "namespaces": namespaces,
            "preserved_event_ids": [e["id"] for e in events],
            "fixture_snapshot_sha256": hashlib.sha256(
                encoded(events).encode()
            ).hexdigest(),
            "pending_graph_event_ids": pending_graph,
            "unresolved_event_ids": unresolved,
            "batches_to_reject": batches,
            "inbox_transport_in_boundary": transport,
            "review_plans_to_complete": plans,
            "review_appointments": appointments,
            "status": ("retiring" if pending_reviews else "retired")
            if inactive
            else "active",
            "blockers": sorted(set(blockers)),
        }
        report["preview_sha256"] = hashlib.sha256(encoded(report).encode()).hexdigest()
        return report

    def _transport(
        self, namespaces: list[str], instance_ref: str, database_id: str
    ) -> list[dict]:
        if self.inbox_root is None:
            raise ValueError("Manual inbox is required.")
        inbox = ManualInbox(self.inbox_root, instance_ref)
        inbox.verify()
        if json.loads(read_bounded(inbox.root / "database.json")) != {
            "database_id": database_id
        }:
            raise ValueError("Manual inbox belongs to another database.")
        transport = []
        for path in sorted((inbox.root / "pending").glob("*.json")):
            payload = read_bounded(path, limit=MAX_TRANSPORT_BYTES)
            digest = hashlib.sha256(payload).hexdigest()
            request = json.loads(payload)
            if (
                path.name != digest + ".json"
                or not isinstance(request, dict)
                or request.get("instance") != instance_ref
                or request.get("action") not in {"submit", "preview", "approve"}
            ):
                raise ValueError("Uninspectable inbox transport.")
            namespace = identifier(request["namespace"])
            submission = identifier(request["submission_id"])
            if namespace in namespaces:
                transport.append(
                    {
                        "sha256": digest,
                        "namespace": namespace,
                        "submission_id": submission,
                        "action": request["action"],
                    }
                )
        return transport

    def deactivate(self, job_key: str, decision: dict, preview_sha256: str) -> dict:
        with instance_lock(self.repository.path), self.repository.transaction() as tx:
            report = self._preview(tx, job_key, decision)
            if report["status"] != "active":
                saved = tx.saved_decision(job_key)[0]
                if saved != encoded(decision):
                    raise ValueError("Scope already retired with a different decision.")
                return report
            if report["preview_sha256"] != preview_sha256 or report["blockers"]:
                raise ValueError(
                    "Unsafe or stale retirement preview; inspect a fresh preview."
                )
            now = self._now().isoformat()
            tx.deactivate(job_key, encoded(decision), now)
            for namespace in report["namespaces"]:
                tx.reject_batches(now, namespace)
                plan = {
                    "state": "complete",
                    "tasks": [],
                    "completion_note": "Scope retired: " + decision["evidence_ref"],
                }
                tx.complete_review_plan(encoded(plan), now, namespace)
            self._audit(tx, job_key, "deactivate", decision, now)
            result = self._preview(tx, job_key, decision)
        self._log(job_key, "deactivate", decision, now)
        return result

    def reactivate(self, job_key: str, operator_ref: str, evidence_ref: str) -> None:
        decision = {"operator_ref": operator_ref, "evidence_ref": evidence_ref}
        if any(
            not isinstance(v, str) or not IDENTIFIER.fullmatch(v)
            for v in decision.values()
        ):
            raise ValueError("Use non-secret operator/evidence identifiers.")
        with instance_lock(self.repository.path), self.repository.transaction() as tx:
            row = tx.retirement(job_key)
            if row is None:
                raise ValueError(
                    "No retirement exists; use explicit future-season configuration."
                )
            if row["reactivated_at"] is not None:
                return
            report = self._preview(tx, job_key, json.loads(row["decision_json"]))
            if report["status"] != "retired":
                raise ValueError(
                    "Complete pending review retirement before reactivation."
                )
            # Authority stayed enabled and reserved throughout retirement. Existing
            # SQL overlap validation therefore remains in force, even after restart.
            now = self._now().isoformat()
            tx.reactivate(now, job_key)
            self._audit(tx, job_key, "reactivate", decision, now)
        self._log(job_key, "reactivate", decision, now)

    def _audit(
        self,
        tx: ScopeRetirementTransaction,
        job_key: str,
        operation: str,
        decision: dict,
        now: str,
    ) -> None:
        tx.append_audit(
            job_key,
            operation,
            encoded(
                {
                    "decision": decision,
                    "calendar_id": self.calendar,
                    "scope": dict(tx.audit_scope(job_key)),
                    "status": "inactive" if operation == "deactivate" else "active",
                }
            ),
            now,
        )

    def _log(self, job_key: str, operation: str, decision: dict, now: str) -> None:
        self.logger.info(
            "Scope lifecycle: job=%s operation=%s effective_at=%s "
            "operator=%s evidence=%s",
            job_key,
            operation,
            now,
            decision["operator_ref"],
            decision["evidence_ref"],
        )
