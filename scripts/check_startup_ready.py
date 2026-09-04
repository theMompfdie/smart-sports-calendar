"""Read-only CI probe for initialization during the current container start.

Run through docker compose exec -T calendar-sync python - <started-at>
with this file on stdin. Read Docker's StartedAt on every probe so a startup
row from before a container restart cannot satisfy readiness.
"""

import os
import sqlite3
import sys
from contextlib import closing
from datetime import datetime
from pathlib import Path


def startup_ready(database_path: Path, container_started_at: str) -> bool:
    started_at = datetime.fromisoformat(container_started_at)
    if started_at.tzinfo is None:
        raise ValueError("Container start time must include a timezone.")
    try:
        with closing(
            sqlite3.connect(
                database_path.resolve().as_uri() + "?mode=ro", timeout=1, uri=True
            )
        ) as connection:
            row = connection.execute(
                "SELECT started_at FROM system_status "
                "WHERE status = 'started' ORDER BY id DESC LIMIT 1"
            ).fetchone()
    except sqlite3.OperationalError:
        # Missing file/table and a busy migration are expected during startup.
        return False
    if row is None:
        return False
    recorded_at = datetime.fromisoformat(row[0])
    return recorded_at.tzinfo is not None and recorded_at >= started_at


if __name__ == "__main__":
    ready = startup_ready(Path(os.environ["DATABASE_PATH"]), sys.argv[1])
    print("Current startup record: " + ("ready" if ready else "pending"))
    sys.exit(0 if ready else 1)
