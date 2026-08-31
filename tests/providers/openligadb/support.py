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

CHAMPIONS_LEAGUE_TEAMS = (
    (7, "Borussia Dortmund", "Dortmund"),
    (16, "VfB Stuttgart", "Stuttgart"),
    (40, "FC Bayern München", "Bayern"),
    (356, "FC Barcelona", "Barcelona"),
    (366, "Fenerbahçe SK", "Fenerbahçe"),
    (370, "FC Liverpool", "Liverpool"),
    (375, "FC Porto", "Porto"),
    (376, "PSV Eindhoven", "PSV"),
    (378, "AS Rom", "AS Rom"),
    (382, "Villarreal CF", "Villarreal CF"),
    (438, "Aston Villa", "Villa"),
    (733, "Inter Mailand", "Inter"),
    (1133, "Real Madrid", "Madrid"),
    (1186, "Shakhtar Donetsk", "Shakhtar Donetsk"),
    (1204, "Lille OSC", "Lille"),
    (1205, "Sporting CP", "Sporting"),
    (1210, "FC Brügge", "Brügge"),
    (1217, "AEK Athen", "AEK Athen"),
    (1484, "Viking", "Viking"),
    (1635, "RB Leipzig", "Leipzig"),
    (1770, "Feyenoord Rotterdam", "Feyenoord"),
    (1804, "Real Betis", "Real Betis"),
    (2281, "Paris St. Germain", "Paris"),
    (2331, "SSC Napoli", ""),
    (2554, "Galatasaray Istanbul", "Galatasaray"),
    (2556, "Manchester United FC", "ManU"),
    (2617, "FC Arsenal", "Arsenal"),
    (4241, "Atletico Madrid", ""),
    (4244, "Manchester City", "Man'City"),
    (4578, "Slavia Prag", "Slavia Prag"),
    (5139, "LASK", "LA"),
    (5699, "Slovan Bratislava", "Bratislava"),
    (5707, "FK Bodö/Glimt", "Bodö/Glimt"),
    (5962, "RC Lens", "Lens"),
    (8787, "Como 1907", "Como 1907"),
    (8798, "Sabah", "Sabah"),
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


def champions_league_payloads(
    *, include_later_stage_fixture: bool = False
) -> tuple[list[dict], list[dict], list[dict]]:
    leagues = [
        {
            "leagueId": 4946,
            "leagueName": "Champions League 2026/2027",
            "leagueShortcut": "ucl",
            "leagueSeason": "2026",
            "sport": {"sportId": 1, "sportName": "Fußball"},
        }
    ]
    group_names = (
        *(f"{order}. Spieltag" for order in range(1, 9)),
        "Playoffs",
        "Achtelfinale Hinspiele",
        "Achtelfinale Rückspiele",
        "Viertelfinale Hinspiele",
        "Viertelfinale Rückspiele",
        "Halbfinale Hinspiele",
        "Halbfinale Rückspiele",
        "Finale",
    )
    groups = [
        {
            "groupID": 50854 + order,
            "groupName": name,
            "groupOrderID": order,
        }
        for order, name in enumerate(group_names, start=1)
    ]
    teams = [
        {"teamId": team_id, "teamName": name, "shortName": short_name}
        for team_id, name, short_name in CHAMPIONS_LEAGUE_TEAMS
    ]
    rotation = teams.copy()
    matchdays: list[list[tuple[dict, dict]]] = []
    for _ in range(8):
        matchdays.append(
            [(rotation[index], rotation[-1 - index]) for index in range(18)]
        )
        rotation = [rotation[0], rotation[-1], *rotation[1:-1]]

    matches: list[dict] = []
    for matchday, pairings in enumerate(matchdays, start=1):
        for home, away in pairings:
            matches.append(
                {
                    "matchID": 140000 + len(matches),
                    "leagueId": 4946,
                    "leagueName": "Champions League 2026/2027",
                    "leagueShortcut": "ucl",
                    "leagueSeason": 2026,
                    "group": deepcopy(groups[matchday - 1]),
                    "team1": deepcopy(home),
                    "team2": deepcopy(away),
                    "matchDateTimeUTC": "2026-09-08T18:45:00Z",
                    "lastUpdateDateTime": "2026-08-16T15:26:22.460",
                    "timeZoneID": "W. Europe Standard Time",
                    "matchIsFinished": False,
                }
            )
    if include_later_stage_fixture:
        later = deepcopy(matches[0])
        later["matchID"] = 150000
        later["group"] = deepcopy(groups[8])
        later["matchDateTimeUTC"] = "2027-01-27T20:00:00Z"
        matches.append(later)
    return leagues, groups, matches
