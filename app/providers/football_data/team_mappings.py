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


def resolve_team_key(provider_name: str) -> str | None:
    normalized = re.sub(r"[^a-z0-9]", "", provider_name.casefold())
    exact = _NORMALIZED_TEAM_MAPPING.get(normalized)
    if exact is not None:
        return exact
    for affix in ("footballclub", "afc", "fc"):
        normalized = normalized.removeprefix(affix).removesuffix(affix)
    return _NORMALIZED_TEAM_MAPPING.get(normalized)
