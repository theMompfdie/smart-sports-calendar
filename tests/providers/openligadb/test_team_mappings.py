from app.providers.openligadb.team_mappings import (
    CHAMPIONS_LEAGUE_TEAM_MAPPINGS,
    DFB_POKAL_TEAM_MAPPINGS,
    NATIONS_LEAGUE_A_TEAM_MAPPINGS_BY_NAME,
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


def test_reviewed_nations_league_mapping_uses_names_without_provider_ids() -> None:
    assert len(NATIONS_LEAGUE_A_TEAM_MAPPINGS_BY_NAME) == 16
    assert len(get_reviewed_team_keys("uefa_nations_league")) == 16
    assert resolve_team_key("uefa_nations_league", 1005, "Deutschland") == "germany"
    assert resolve_team_key("uefa_nations_league", 9999, "Deutschland") == "germany"
    assert resolve_team_key("uefa_nations_league", 1005, "Germany") is None


def test_reviewed_champions_league_mapping_has_36_distinct_identities() -> None:
    assert len(CHAMPIONS_LEAGUE_TEAM_MAPPINGS) == 36
    assert len(get_reviewed_team_keys("uefa_champions_league")) == 36
    assert (
        resolve_team_key("uefa_champions_league", 1217, "AEK Athen")
        == "aek_athens"
    )
    assert resolve_team_key("uefa_champions_league", 1217, "AEK Athens") is None


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


def test_dfb_pokal_mapping_accepts_only_reviewed_jeddeloh_aliases() -> None:
    assert resolve_team_key("dfb_pokal", 4762, "SSV Jeddeloh II") == "ssv_jeddeloh"
    assert resolve_team_key("dfb_pokal", 4762, "SSV Jeddeloh 2") == "ssv_jeddeloh"
    assert resolve_team_key("dfb_pokal", 4762, "  SSV Jeddeloh II  ") == (
        "ssv_jeddeloh"
    )
    assert resolve_team_key("dfb_pokal", 4762, "SSV Jeddeloh") is None
    assert resolve_team_key("second_bundesliga", 4762, "SSV Jeddeloh II") is None


def test_dfb_pokal_mapping_accepts_only_reviewed_saarbruecken_name() -> None:
    assert resolve_team_key("dfb_pokal", 3078, "1. FC Saarbrücken") == "fc_saarbruecken"
    assert resolve_team_key("dfb_pokal", 3078, "1.FC Saarbrücken") is None
