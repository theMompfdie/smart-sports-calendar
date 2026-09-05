"""Standalone local preview; no application bootstrap, credentials or writes."""

import argparse
import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path

from app.application.manual_preview_service import (
    ManualPreviewService,
    parse_preview_configuration,
)
from app.database.manual_preview_repository import ManualPreviewRepository
from app.imports.manual_files import read_bounded
from app.imports.manual_manifest import ManifestValidationError


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        configuration = parse_preview_configuration(read_bounded(args.profile))
        report = ManualPreviewService(ManualPreviewRepository(args.database)).preview(
            read_bounded(args.manifest), configuration
        )
    except ManifestValidationError as error:
        print(json.dumps({"accepted": False, "error": str(error)}))
        return 2
    except (OSError, sqlite3.Error, ValueError):
        print(
            json.dumps(
                {
                    "accepted": False,
                    "error": "Input or database is unavailable or incompatible.",
                }
            )
        )
        return 2
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=True, sort_keys=True))
    return 0 if report.accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())
