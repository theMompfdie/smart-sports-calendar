"""Stopped-owner maintenance CLI for reviewed competition-season retirement."""

import argparse
import json
import sqlite3
from pathlib import Path

from app.application.scope_retirement_service import ScopeRetirementService
from app.database.scope_retirement_repository import ScopeRetirementRepository
from app.imports.manual_files import read_bounded


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preview", "deactivate", "reactivate"))
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--calendar", required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--inbox", type=Path)
    parser.add_argument("--decision", type=Path)
    parser.add_argument("--preview-sha256")
    parser.add_argument("--operator-ref")
    parser.add_argument("--evidence-ref")
    args = parser.parse_args(argv)
    try:
        service = ScopeRetirementService(
            ScopeRetirementRepository(args.database),
            args.calendar,
            inbox_root=args.inbox,
        )
        if args.action == "reactivate":
            service.reactivate(args.job, args.operator_ref, args.evidence_ref)
            print(json.dumps({"job_key": args.job, "status": "reactivated"}))
        else:
            if args.decision is None:
                raise ValueError("--decision is required for preview/deactivate.")
            decision = json.loads(read_bounded(args.decision))
            if not isinstance(decision, dict):
                raise ValueError("Decision must be a JSON object.")
            if args.action == "deactivate":
                if args.preview_sha256 is None:
                    raise ValueError("--preview-sha256 is required for deactivate.")
                report = service.deactivate(args.job, decision, args.preview_sha256)
            else:
                report = service.preview(args.job, decision)
            print(json.dumps(report, indent=2))
        return 0
    except (OSError, ValueError, TypeError, RuntimeError, sqlite3.Error) as error:
        parser.exit(2, f"Retirement refused: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
