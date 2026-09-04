"""Secret-safe local CLI for global Outlook presentation invalidation."""

import argparse
import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path

from app.database.calendar_event_mappings_repository import (
    CalendarEventMappingsRepository,
)
from app.database.database import Database


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Queue every live Outlook event mapping after a global presentation "
            "template or policy change."
        )
    )
    parser.add_argument(
        "--database",
        required=True,
        type=Path,
        help="Explicit path to the target SMART Sports Calendar SQLite database.",
    )
    parser.add_argument(
        "--invalidate-all",
        action="store_true",
        required=True,
        help="Increment the desired presentation revision for every live mapping.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        Database(args.database).initialize()
        affected = CalendarEventMappingsRepository(
            args.database
        ).invalidate_all_presentations()
    except (OSError, sqlite3.Error):
        parser.exit(
            status=1,
            message="Presentation invalidation failed: database operation failed.\n",
        )
    print(json.dumps({"affected_mappings": affected}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
