from app.database.participants_catalog import NFL_2026_TEAMS

NFLVERSE_TEAM_MAPPING = {
    abbreviation: participant_key
    for participant_key, _, _, abbreviation in NFL_2026_TEAMS
}


def resolve_team_key(abbreviation: str) -> str | None:
    return NFLVERSE_TEAM_MAPPING.get(abbreviation)


def get_reviewed_team_keys() -> frozenset[str]:
    return frozenset(NFLVERSE_TEAM_MAPPING.values())
