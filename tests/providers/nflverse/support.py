import csv
import io
from datetime import date, timedelta

from app.providers.nflverse.team_mappings import NFLVERSE_TEAM_MAPPING


def schedule_rows() -> list[dict[str, str]]:
    teams = list(NFLVERSE_TEAM_MAPPING)
    rotating = teams[:]
    rows: list[dict[str, str]] = []
    game_number = 0
    for round_index in range(17):
        week = round_index + 1
        for index in range(16):
            away = rotating[index]
            home = rotating[-index - 1]
            game_number += 1
            effective_week = 18 if round_index == 16 and index == 0 else week
            gameday = date(2026, 9, 10) + timedelta(weeks=effective_week - 1)
            rows.append(
                {
                    "game_id": f"2026_{game_number:03d}_{away}_{home}",
                    "season": "2026",
                    "game_type": "REG",
                    "week": str(effective_week),
                    "gameday": gameday.isoformat(),
                    "gametime": "20:00",
                    "away_team": away,
                    "home_team": home,
                    "espn": str(100000 + game_number),
                    "old_game_id": "",
                    "gsis": "",
                }
            )
        rotating = [rotating[0], rotating[-1], *rotating[1:-1]]
    return rows


def csv_bytes(rows: list[dict[str, str]] | None = None) -> bytes:
    selected = rows if rows is not None else schedule_rows()
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(selected[0]))
    writer.writeheader()
    writer.writerows(selected)
    return buffer.getvalue().encode()
