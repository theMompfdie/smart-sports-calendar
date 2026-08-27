from app.providers.openligadb.team_mappings import (
    DFB_POKAL_TEAM_MAPPINGS,
    SECOND_BUNDESLIGA_TEAM_MAPPINGS,
    get_reviewed_team_keys,
    resolve_team_key,
)


def test_reviewed_dfb_pokal_mapping_has_64_distinct_identities() -> None:
    assert len(DFB_POKAL_TEAM_MAPPINGS) == 64
    assert len(get_reviewed_team_keys("dfb_pokal")) == 64


def test_reviewed_second_bundesliga_mapping_has_18_distinct_identities() -> None:
    assert len(SECOND_BUNDESLIGA_TEAM_MAPPINGS) == 18
    assert len(get_reviewed_team_keys("second_bundesliga")) == 18


def test_team_mapping_requires_the_reviewed_id_and_name_pair() -> None:
    assert resolve_team_key("dfb_pokal", 5712, "SC St. Tönis") == "sc_st_toenis"
    assert (
        resolve_team_key("dfb_pokal", 91, "Eintracht Frankfurt")
        == "eintracht_frankfurt"
    )
    assert resolve_team_key("dfb_pokal", 5712, "Changed name") is None
    assert resolve_team_key("dfb_pokal", 999999, "SC St. Tönis") is None
    assert (
        resolve_team_key("second_bundesliga", 199, "1. FC Heidenheim 1846")
        == "fc_heidenheim"
    )
    assert resolve_team_key("second_bundesliga", 199, "Changed name") is None


def test_dfb_pokal_mapping_accepts_only_reviewed_saarbruecken_name() -> None:
    assert resolve_team_key("dfb_pokal", 3078, "1. FC Saarbrücken") == "fc_saarbruecken"
    assert resolve_team_key("dfb_pokal", 3078, "1.FC Saarbrücken") is None
