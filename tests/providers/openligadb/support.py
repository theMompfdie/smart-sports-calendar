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


SECOND_BUNDESLIGA_TEAMS = (
    (36, "VfL Osnabrück", "Osnabrück"),
    (54, "Hertha BSC", "Hertha"),
    (55, "Hannover 96", "Hannover"),
    (74, "Eintracht Braunschweig", "Braunschweig"),
    (76, "1. FC Kaiserslautern", "Kaiserslautern"),
    (78, "1. FC Magdeburg", "Magdeburg"),
    (79, "1. FC Nürnberg", "Nürnberg"),
    (83, "DSC Arminia Bielefeld", "Bielefeld"),
    (93, "Energie Cottbus", "Cottbus"),
    (98, "FC St. Pauli", "St. Pauli"),
    (104, "Holstein Kiel", "Kiel"),
    (105, "Karlsruher SC", "Karlsruhe"),
    (115, "SpVgg Greuther Fürth", "Fürth"),
    (118, "SV Darmstadt 98", "Darmstadt"),
    (129, "VfL Bochum", "Bochum"),
    (131, "VfL Wolfsburg", "Wolfsburg"),
    (177, "Dynamo Dresden", "Dresden"),
    (199, "1. FC Heidenheim 1846", "Heidenheim"),
)

NATIONS_LEAGUE_A_TEAMS = (
    (1001, "Frankreich", "Frankreich"),
    (1002, "Italien", "Italien"),
    (1003, "Belgien", "Belgien"),
    (1004, "Türkei", "Türkei"),
    (1005, "Deutschland", "Deutschland"),
    (1006, "Niederlande", "Niederlande"),
    (1007, "Serbien", "Serbien"),
    (1008, "Griechenland", "Griechenland"),
    (1009, "Spanien", "Spanien"),
    (1010, "Kroatien", "Kroatien"),
    (1011, "England", "England"),
    (1012, "Tschechien", "Tschechien"),
    (1013, "Portugal", "Portugal"),
    (1014, "Dänemark", "Dänemark"),
    (1015, "Norwegen", "Norwegen"),
    (1016, "Wales", "Wales"),
)


def second_bundesliga_payloads() -> tuple[list[dict], list[dict], list[dict]]:
    leagues = [
        {
            "leagueId": 4938,
            "leagueName": "2. Fußball-Bundesliga 2026/2027",
            "leagueShortcut": "bl2",
            "leagueSeason": "2026",
            "sport": {"sportId": 1, "sportName": "Fußball"},
        }
    ]
    groups = [
        {
            "groupID": 60000 + order,
            "groupName": f"{order}. Spieltag",
            "groupOrderID": order,
        }
        for order in range(1, 35)
    ]
    teams = [
        {"teamId": team_id, "teamName": name, "shortName": short_name}
        for team_id, name, short_name in SECOND_BUNDESLIGA_TEAMS
    ]
    rotation = teams.copy()
    first_half: list[list[tuple[dict, dict]]] = []
    for _ in range(17):
        first_half.append(
            [(rotation[index], rotation[-1 - index]) for index in range(9)]
        )
        rotation = [rotation[0], rotation[-1], *rotation[1:-1]]
    second_half = [[(away, home) for home, away in matchday] for matchday in first_half]
    matchdays = [*first_half, *second_half]
    matches: list[dict] = []
    for matchday, pairings in enumerate(matchdays, start=1):
        for slot, (home, away) in enumerate(pairings):
            matches.append(
                {
                    "matchID": 90000 + (matchday - 1) * 9 + slot,
                    "leagueId": 4938,
                    "leagueName": "2. Fußball-Bundesliga 2026/2027",
                    "leagueShortcut": "bl2",
                    "leagueSeason": 2026,
                    "group": deepcopy(groups[matchday - 1]),
                    "team1": deepcopy(home),
                    "team2": deepcopy(away),
                    "matchDateTimeUTC": "2026-08-07T18:30:00Z",
                    "lastUpdateDateTime": "2026-08-16T15:26:22.460",
                    "timeZoneID": (
                        "" if len(matches) < 18 else "W. Europe Standard Time"
                    ),
                    "matchIsFinished": len(matches) < 18,
                }
            )
    return leagues, groups, matches


def nations_league_a_payloads(
    *, include_later_stage_fixture: bool = False
) -> tuple[list[dict], list[dict], list[dict]]:
    leagues = [
        {
            "leagueId": 5978,
            "leagueName": "Nations League A 2026",
            "leagueShortcut": "nla",
            "leagueSeason": "2026",
            "sport": {"sportId": 1, "sportName": "Fußball"},
        }
    ]
    group_names = (
        "Gruppe A",
        "Gruppe B",
        "Gruppe C",
        "Gruppe D",
        "Viertelfinale Hinspiele",
        "Viertelfinale Rückspiele",
        "Halbfinale",
        "Endspiel/Platz 3",
    )
    groups = [
        {
            "groupID": 52000 + order,
            "groupName": name,
            "groupOrderID": order,
        }
        for order, name in enumerate(group_names, start=1)
    ]
    teams = [
        {"teamId": team_id, "teamName": name, "shortName": short_name}
        for team_id, name, short_name in NATIONS_LEAGUE_A_TEAMS
    ]
    matches: list[dict] = []
    for group_order in range(1, 5):
        group_teams = teams[(group_order - 1) * 4 : group_order * 4]
        for home in group_teams:
            for away in group_teams:
                if home == away:
                    continue
                matches.append(
                    {
                        "matchID": 120000 + len(matches),
                        "leagueId": 5978,
                        "leagueName": "Nations League A 2026",
                        "leagueShortcut": "nla",
                        "leagueSeason": 2026,
                        "group": deepcopy(groups[group_order - 1]),
                        "team1": deepcopy(home),
                        "team2": deepcopy(away),
                        "matchDateTimeUTC": (
                            f"2026-09-{23 + group_order:02d}T18:45:00Z"
                        ),
                        "lastUpdateDateTime": "2026-08-16T15:26:22.460",
                        "timeZoneID": "W. Europe Standard Time",
                        "matchIsFinished": False,
                    }
                )
    if include_later_stage_fixture:
        later = deepcopy(matches[0])
        later["matchID"] = 130000
        later["group"] = deepcopy(groups[4])
        later["matchDateTimeUTC"] = "2026-10-01T18:45:00Z"
        matches.append(later)
    return leagues, groups, matches
