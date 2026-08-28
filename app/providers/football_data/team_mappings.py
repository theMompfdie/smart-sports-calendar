"""Reviewed deterministic team names for the 2026/27 Premier League catalog."""

import re

PREMIER_LEAGUE_TEAM_NAME_MAPPING: dict[str, str] = {
    "Arsenal FC": "arsenal",
    "Aston Villa FC": "aston_villa",
    "AFC Bournemouth": "bournemouth",
    "Brentford FC": "brentford",
    "Brighton & Hove Albion FC": "brighton_and_hove_albion",
    "Chelsea FC": "chelsea",
    "Coventry City FC": "coventry_city",
    "Crystal Palace FC": "crystal_palace",
    "Everton FC": "everton",
    "Fulham FC": "fulham",
    "Hull City AFC": "hull_city",
    "Ipswich Town FC": "ipswich_town",
    "Leeds United FC": "leeds_united",
    "Liverpool FC": "liverpool",
    "Manchester City FC": "manchester_city",
    "Manchester United FC": "manchester_united",
    "Newcastle United FC": "newcastle_united",
    "Nottingham Forest FC": "nottingham_forest",
    "Sunderland AFC": "sunderland",
    "Tottenham Hotspur FC": "tottenham_hotspur",
}

BUNDESLIGA_TEAM_NAME_MAPPING: dict[str, str] = {
    "1. FC Köln": "fc_koeln",
    "1. FC Union Berlin": "fc_union_berlin",
    "1. FSV Mainz 05": "fsv_mainz_05",
    "Bayer 04 Leverkusen": "bayer_04_leverkusen",
    "Borussia Dortmund": "borussia_dortmund",
    "Borussia Mönchengladbach": "borussia_moenchengladbach",
    "Eintracht Frankfurt": "eintracht_frankfurt",
    "FC Augsburg": "fc_augsburg",
    "FC Bayern München": "fc_bayern_muenchen",
    "FC Schalke 04": "fc_schalke_04",
    "Hamburger SV": "hamburger_sv",
    "RB Leipzig": "rb_leipzig",
    "SC Freiburg": "sc_freiburg",
    "SC Paderborn 07": "sc_paderborn_07",
    "SV 07 Elversberg": "sv_elversberg",
    "SV Werder Bremen": "werder_bremen",
    "TSG 1899 Hoffenheim": "tsg_hoffenheim",
    "VfB Stuttgart": "vfb_stuttgart",
}

CHAMPIONSHIP_TEAM_NAME_MAPPING: dict[str, str] = {
    "Birmingham City FC": "birmingham_city",
    "Blackburn Rovers FC": "blackburn_rovers",
    "Bolton Wanderers FC": "bolton_wanderers",
    "Bristol City FC": "bristol_city",
    "Burnley FC": "burnley",
    "Cardiff City FC": "cardiff_city",
    "Charlton Athletic FC": "charlton_athletic",
    "Derby County FC": "derby_county",
    "Lincoln City FC": "lincoln_city",
    "Middlesbrough FC": "middlesbrough",
    "Millwall FC": "millwall",
    "Norwich City FC": "norwich_city",
    "Portsmouth FC": "portsmouth",
    "Preston North End FC": "preston_north_end",
    "Queens Park Rangers FC": "queens_park_rangers",
    "Sheffield United FC": "sheffield_united",
    "Southampton FC": "southampton",
    "Stoke City FC": "stoke_city",
    "Swansea City AFC": "swansea_city",
    "Watford FC": "watford",
    "West Bromwich Albion FC": "west_bromwich_albion",
    "West Ham United FC": "west_ham_united",
    "Wolverhampton Wanderers FC": "wolverhampton_wanderers",
    "Wrexham AFC": "wrexham",
}

REVIEWED_TEAM_NAME_MAPPINGS = {
    "premier_league": PREMIER_LEAGUE_TEAM_NAME_MAPPING,
    "bundesliga": BUNDESLIGA_TEAM_NAME_MAPPING,
    "championship": CHAMPIONSHIP_TEAM_NAME_MAPPING,
}

_NORMALIZED_TEAM_MAPPING = {
    re.sub(r"[^a-z0-9]", "", name.casefold()): key
    for name, key in PREMIER_LEAGUE_TEAM_NAME_MAPPING.items()
}
_NORMALIZED_TEAM_MAPPING.update(
    {
        "arsenal": "arsenal",
        "astonvilla": "aston_villa",
        "bournemouth": "bournemouth",
        "brentford": "brentford",
        "brightonhovealbion": "brighton_and_hove_albion",
        "chelsea": "chelsea",
        "coventrycity": "coventry_city",
        "crystalpalace": "crystal_palace",
        "everton": "everton",
        "fulham": "fulham",
        "hullcity": "hull_city",
        "ipswichtown": "ipswich_town",
        "leedsunited": "leeds_united",
        "liverpool": "liverpool",
        "manchestercity": "manchester_city",
        "manchesterunited": "manchester_united",
        "newcastleunited": "newcastle_united",
        "nottinghamforest": "nottingham_forest",
        "sunderland": "sunderland",
        "tottenhamhotspur": "tottenham_hotspur",
    }
)

_NORMALIZED_BUNDESLIGA_TEAM_MAPPING = {
    re.sub(r"[^a-z0-9]", "", name.casefold()): key
    for name, key in BUNDESLIGA_TEAM_NAME_MAPPING.items()
}
_NORMALIZED_BUNDESLIGA_TEAM_MAPPING.update(
    {
        "1fckoln": "fc_koeln",
        "kln": "fc_koeln",
        "koeln": "fc_koeln",
        "koln": "fc_koeln",
        "unionberlin": "fc_union_berlin",
        "mainz": "fsv_mainz_05",
        "mainz05": "fsv_mainz_05",
        "leverkusen": "bayer_04_leverkusen",
        "dortmund": "borussia_dortmund",
        "mgladbach": "borussia_moenchengladbach",
        "monchengladbach": "borussia_moenchengladbach",
        "frankfurt": "eintracht_frankfurt",
        "augsburg": "fc_augsburg",
        "bayern": "fc_bayern_muenchen",
        "bayernmunchen": "fc_bayern_muenchen",
        "schalke": "fc_schalke_04",
        "schalke04": "fc_schalke_04",
        "hsv": "hamburger_sv",
        "freiburg": "sc_freiburg",
        "scpaderborn": "sc_paderborn_07",
        "paderborn": "sc_paderborn_07",
        "elversberg": "sv_elversberg",
        "bremen": "werder_bremen",
        "hoffenheim": "tsg_hoffenheim",
        "stuttgart": "vfb_stuttgart",
    }
)

_NORMALIZED_CHAMPIONSHIP_TEAM_MAPPING = {
    re.sub(r"[^a-z0-9]", "", name.casefold()): key
    for name, key in CHAMPIONSHIP_TEAM_NAME_MAPPING.items()
}
_NORMALIZED_CHAMPIONSHIP_TEAM_MAPPING.update(
    {
        "birmingham": "birmingham_city",
        "blackburn": "blackburn_rovers",
        "bolton": "bolton_wanderers",
        "bristolcity": "bristol_city",
        "burnley": "burnley",
        "cardiff": "cardiff_city",
        "charlton": "charlton_athletic",
        "derbycounty": "derby_county",
        "lincolncity": "lincoln_city",
        "middlesbrough": "middlesbrough",
        "millwall": "millwall",
        "norwich": "norwich_city",
        "portsmouth": "portsmouth",
        "prestonne": "preston_north_end",
        "qpr": "queens_park_rangers",
        "sheffieldutd": "sheffield_united",
        "southampton": "southampton",
        "stoke": "stoke_city",
        "swansea": "swansea_city",
        "watford": "watford",
        "westbrom": "west_bromwich_albion",
        "westham": "west_ham_united",
        "wolverhampton": "wolverhampton_wanderers",
        "wrexham": "wrexham",
    }
)

TEAM_NAME_MAPPINGS: dict[str, dict[str, str]] = {
    "premier_league": _NORMALIZED_TEAM_MAPPING,
    "bundesliga": _NORMALIZED_BUNDESLIGA_TEAM_MAPPING,
    "championship": _NORMALIZED_CHAMPIONSHIP_TEAM_MAPPING,
}


def resolve_team_key(competition_key: str, provider_name: str) -> str | None:
    mapping = TEAM_NAME_MAPPINGS.get(competition_key)
    if mapping is None:
        return None
    normalized = re.sub(r"[^a-z0-9]", "", provider_name.casefold())
    exact = mapping.get(normalized)
    if exact is not None:
        return exact
    for affix in ("footballclub", "afc", "fc"):
        normalized = normalized.removeprefix(affix).removesuffix(affix)
    return mapping.get(normalized)


def get_reviewed_team_keys(competition_key: str) -> frozenset[str] | None:
    mapping = REVIEWED_TEAM_NAME_MAPPINGS.get(competition_key)
    if mapping is None:
        return None
    return frozenset(mapping.values())
