from app.providers.openligadb.team_mappings import (
    DFB_POKAL_TEAM_MAPPINGS,
    get_reviewed_team_keys,
    resolve_team_key,
)


def test_reviewed_dfb_pokal_mapping_has_64_distinct_identities() -> None:
    assert len(DFB_POKAL_TEAM_MAPPINGS) == 64
    assert len(get_reviewed_team_keys()) == 64


def test_team_mapping_requires_the_reviewed_id_and_name_pair() -> None:
    assert resolve_team_key(5712, "SC St. Tönis") == "sc_st_toenis"
    assert resolve_team_key(91, "Eintracht Frankfurt") == "eintracht_frankfurt"
    assert resolve_team_key(5712, "Changed name") is None
    assert resolve_team_key(999999, "SC St. Tönis") is None
