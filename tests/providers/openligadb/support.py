from copy import deepcopy
from datetime import UTC, datetime

FETCHED_AT = datetime(2026, 8, 18, 19, 0, tzinfo=UTC)


def payloads() -> tuple[list[dict], list[dict], list[dict]]:
    leagues = [
        {
            "leagueId": 4945,
            "leagueName": "DFB Pokal 2026/2027",
            "leagueShortcut": "dfb",
            "leagueSeason": "2026",
            "sport": {"sportId": 1, "sportName": "Fußball"},
        }
    ]
    groups = [
        {
            "groupID": 100 + order,
            "groupName": f"Provider round {order}",
            "groupOrderID": order,
        }
        for order in range(1, 7)
    ]
    matches = [
        {
            "matchID": 7001,
            "leagueId": 4945,
            "leagueName": "DFB Pokal 2026/2027",
            "leagueShortcut": "dfb",
            "leagueSeason": 2026,
            "group": deepcopy(groups[0]),
            "team1": {
                "teamId": 5712,
                "teamName": "SC St. Tönis",
                "shortName": "St. Tönis",
                "teamIconUrl": "https://example.test/not-imported.png",
            },
            "team2": {
                "teamId": 91,
                "teamName": "Eintracht Frankfurt",
                "shortName": "Frankfurt",
            },
            "matchDateTimeUTC": "2026-08-21T18:00:00Z",
            "lastUpdateDateTime": "2026-08-17T08:00:00",
            "timeZoneID": "W. Europe Standard Time",
            "matchIsFinished": False,
        }
    ]
    return leagues, groups, matches
