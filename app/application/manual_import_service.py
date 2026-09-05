"""Operator-reviewed manual batch lifecycle; Microsoft Graph stays downstream."""

import json
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime

from app.application.manual_preview_service import (
    PreviewConfiguration,
    PreviewReport,
    _json,
    manual_fixture_record,
    parse_preview_configuration,
    plan_preview,
    validate_preview_approval,
)
from app.database.fixture_import_repository import FixtureImportScopeRecord
from app.database.manual_import_repository import ManualImportRepository
from app.domain.competition_lifecycle import (
    CompetitionLifecycleScope,
    FixtureObservationScopeKind,
)
from app.imports.manual_manifest import parse_approval, parse_manifest


class ManualImportService:
    def __init__(
        self,
        repository: ManualImportRepository,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository
        self.clock = clock or (lambda: datetime.now(UTC))

    def _now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise ValueError("Manual import clock must use aware UTC.")
        return value

    def configure(self, configuration: PreviewConfiguration) -> None:
        """Explicit operator configuration; never run from an incoming package."""
        profile = configuration.profile
        payload = _json(
            {
                "instance_ref": configuration.instance_ref,
                "namespace": profile.namespace,
                "scope": asdict(profile.scope),
                "competition_format": profile.competition_format,
                "boundaries": sorted(
                    (asdict(b) for b in profile.boundaries), key=_json
                ),
            }
        )
        # Validate programmatically constructed configurations as strictly as CLI input.
        parsed = parse_preview_configuration(payload.encode("utf-8"))
        with self.repository.transaction() as tx:
            tx.configure(
                parsed.profile, parsed.instance_ref, payload, self._now().isoformat()
            )

    def receive(self, payload: bytes) -> str:
        manifest = parse_manifest(payload)
        with self.repository.transaction() as tx:
            return tx.receive(manifest, self._now().isoformat())

    @staticmethod
    def _reviewed(batch) -> PreviewReport:
        if batch["preview_json"] is None or batch["preview_sha256"] is None:
            raise ValueError("Package has no reviewable preview.")
        return PreviewReport(
            batch["preview_json"],
            batch["preview_sha256"],
            json.loads(batch["preview_json"])["accepted"],
        )

    def prepare(self, submission_id: str) -> PreviewReport:
        with self.repository.transaction() as tx:
            batch = tx.batch(submission_id)
            if batch["state"] == "APPLIED":
                return self._reviewed(batch)
            manifest = parse_manifest(batch["payload"])
            configuration = parse_preview_configuration(tx.profile(manifest.namespace))
            report = plan_preview(manifest, configuration, tx.snapshot(manifest))
            tx.save_preview(
                submission_id,
                report.payload,
                report.fingerprint,
                report.accepted,
                self._now().isoformat(),
            )
            return report

    def approve(self, submission_id: str, payload: bytes) -> None:
        stale = False
        with self.repository.transaction() as tx:
            batch = tx.batch(submission_id)
            manifest = parse_manifest(batch["payload"])
            approval = parse_approval(payload, manifest)
            if approval.approved_at > self._now():
                raise ValueError("Approval time is in the future.")
            if batch["state"] == "APPLIED":
                return
            if batch["state"] not in {"AWAITING_APPROVAL", "APPROVED"}:
                raise ValueError("Package is not awaiting approval.")
            configuration = parse_preview_configuration(tx.profile(manifest.namespace))
            current = plan_preview(manifest, configuration, tx.snapshot(manifest))
            try:
                validate_preview_approval(
                    approval, manifest, self._reviewed(batch), current, configuration
                )
            except ValueError:
                tx.needs_review(submission_id, self._now().isoformat())
                stale = True
            else:
                tx.approve(submission_id, payload, self._now().isoformat())
        if stale:
            raise ValueError("Package needs a new preview and approval.")

    def apply(self, submission_id: str) -> dict:
        stale = False
        receipt = None
        with self.repository.transaction() as tx:
            batch = tx.batch(submission_id)
            if batch["state"] == "APPLIED":
                return json.loads(tx.receipt(submission_id))
            if batch["state"] != "APPROVED" or batch["approval_payload"] is None:
                raise ValueError("Package has no explicit approval.")
            manifest = parse_manifest(batch["payload"])
            configuration = parse_preview_configuration(tx.profile(manifest.namespace))
            approval = parse_approval(batch["approval_payload"], manifest)
            state = tx.snapshot(manifest)
            current = plan_preview(manifest, configuration, state)
            try:
                validate_preview_approval(
                    approval, manifest, self._reviewed(batch), current, configuration
                )
            except ValueError:
                tx.needs_review(submission_id, self._now().isoformat())
                stale = True
            else:
                sources = [
                    row
                    for row in state.sources
                    if row["source_key"] == "manual" and row["is_active"]
                ]
                if len(sources) != 1:
                    raise ValueError("Manual source is not registered and active.")
                records = tuple(
                    manual_fixture_record(manifest, f, state) for f in manifest.fixtures
                )
                scope = FixtureImportScopeRecord(
                    state.catalog["competition_id"],
                    state.catalog["season_id"],
                    None,
                    None,
                    True,
                    CompetitionLifecycleScope(
                        configuration.profile.competition_format,
                        FixtureObservationScopeKind.PARTIAL,
                    ),
                    False,
                    manifest.submission_id,
                    manifest.provenance.observed_at,
                )
                result = tx.import_records(
                    sources[0]["id"], records, scope, manifest.namespace
                )
                reviewed_items = current.to_dict()["fixtures"]
                if [
                    (item.external_id, item.decision.value) for item in result.items
                ] != [
                    (manifest.namespace + ":" + item["fixture_id"], item["decision"])
                    for item in reviewed_items
                ]:
                    raise ValueError("Canonical outcome differs from reviewed plan.")
                now = self._now().isoformat()
                receipt = {
                    "submission_id": submission_id,
                    "namespace": manifest.namespace,
                    "import_type": manifest.import_type,
                    "schema_version": manifest.schema_version,
                    "manifest_sha256": manifest.fingerprint,
                    "preview_sha256": current.fingerprint,
                    "provenance": asdict(manifest.provenance),
                    "approval": asdict(approval),
                    "items": [asdict(item) for item in result.items],
                    "counts": current.to_dict()["summary"],
                    "committed_at": now,
                    "canonical_status": "committed",
                    "outlook_status": "pending",
                    "review_plan": asdict(manifest.review_plan),
                }
                encoded = _json(receipt)
                tx.complete(manifest, encoded, _json(asdict(manifest.review_plan)), now)
                receipt = json.loads(encoded)
        if stale:
            raise ValueError("Package needs a new preview and approval.")
        if receipt is None:
            raise AssertionError("Successful apply must return a receipt.")
        return receipt
