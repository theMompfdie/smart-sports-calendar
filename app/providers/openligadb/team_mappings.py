from dataclasses import dataclass


@dataclass(frozen=True)
class OpenLigaDBTeamMapping:
    participant_key: str
    provider_name: str
    provider_name_aliases: tuple[str, ...] = ()

    def accepts_provider_name(self, provider_name: str) -> bool:
        normalized_name = provider_name.strip()
        return normalized_name == self.provider_name or (
            normalized_name in self.provider_name_aliases
        )


DFB_POKAL_TEAM_MAPPINGS: dict[int, OpenLigaDBTeamMapping] = {
    6: OpenLigaDBTeamMapping("bayer_04_leverkusen", "Bayer 04 Leverkusen"),
    7: OpenLigaDBTeamMapping("borussia_dortmund", "Borussia Dortmund"),
    9: OpenLigaDBTeamMapping("fc_schalke_04", "FC Schalke 04"),
    16: OpenLigaDBTeamMapping("vfb_stuttgart", "VfB Stuttgart"),
    31: OpenLigaDBTeamMapping("sc_paderborn_07", "SC Paderborn 07"),
    36: OpenLigaDBTeamMapping("vfl_osnabrueck", "VfL Osnabrück"),
    40: OpenLigaDBTeamMapping("fc_bayern_muenchen", "FC Bayern München"),
    54: OpenLigaDBTeamMapping("hertha_bsc", "Hertha BSC"),
    55: OpenLigaDBTeamMapping("hannover_96", "Hannover 96"),
    65: OpenLigaDBTeamMapping("fc_koeln", "1. FC Köln"),
    66: OpenLigaDBTeamMapping("erzgebirge_aue", "Erzgebirge Aue"),
    69: OpenLigaDBTeamMapping("carl_zeiss_jena", "FC Carl Zeiss Jena"),
    74: OpenLigaDBTeamMapping("eintracht_braunschweig", "Eintracht Braunschweig"),
    76: OpenLigaDBTeamMapping("fc_kaiserslautern", "1. FC Kaiserslautern"),
    78: OpenLigaDBTeamMapping("fc_magdeburg", "1. FC Magdeburg"),
    79: OpenLigaDBTeamMapping("fc_nuernberg", "1. FC Nürnberg"),
    80: OpenLigaDBTeamMapping("fc_union_berlin", "1. FC Union Berlin"),
    81: OpenLigaDBTeamMapping("fsv_mainz_05", "1. FSV Mainz 05"),
    83: OpenLigaDBTeamMapping("arminia_bielefeld", "DSC Arminia Bielefeld"),
    87: OpenLigaDBTeamMapping("borussia_moenchengladbach", "Borussia Mönchengladbach"),
    91: OpenLigaDBTeamMapping("eintracht_frankfurt", "Eintracht Frankfurt"),
    93: OpenLigaDBTeamMapping("energie_cottbus", "Energie Cottbus"),
    95: OpenLigaDBTeamMapping("fc_augsburg", "FC Augsburg"),
    98: OpenLigaDBTeamMapping("fc_st_pauli", "FC St. Pauli"),
    100: OpenLigaDBTeamMapping("hamburger_sv", "Hamburger SV"),
    102: OpenLigaDBTeamMapping("hansa_rostock", "Hansa Rostock"),
    104: OpenLigaDBTeamMapping("holstein_kiel", "Holstein Kiel"),
    105: OpenLigaDBTeamMapping("karlsruher_sc", "Karlsruher SC"),
    107: OpenLigaDBTeamMapping("msv_duisburg", "MSV Duisburg"),
    109: OpenLigaDBTeamMapping("rot_weiss_essen", "Rot-Weiss Essen"),
    112: OpenLigaDBTeamMapping("sc_freiburg", "SC Freiburg"),
    114: OpenLigaDBTeamMapping("sc_verl", "SC Verl"),
    115: OpenLigaDBTeamMapping("greuther_fuerth", "SpVgg Greuther Fürth"),
    118: OpenLigaDBTeamMapping("sv_darmstadt_98", "SV Darmstadt 98"),
    125: OpenLigaDBTeamMapping("tsv_1860_muenchen", "TSV 1860 München"),
    129: OpenLigaDBTeamMapping("vfl_bochum", "VfL Bochum"),
    131: OpenLigaDBTeamMapping("vfl_wolfsburg", "VfL Wolfsburg"),
    134: OpenLigaDBTeamMapping("werder_bremen", "SV Werder Bremen"),
    174: OpenLigaDBTeamMapping("wehen_wiesbaden", "SV Wehen Wiesbaden"),
    175: OpenLigaDBTeamMapping("tsg_hoffenheim", "TSG Hoffenheim"),
    177: OpenLigaDBTeamMapping("dynamo_dresden", "Dynamo Dresden"),
    185: OpenLigaDBTeamMapping("fortuna_duesseldorf", "Fortuna Düsseldorf"),
    188: OpenLigaDBTeamMapping("preussen_muenster", "Preußen Münster"),
    198: OpenLigaDBTeamMapping("sv_elversberg", "SV 07 Elversberg"),
    199: OpenLigaDBTeamMapping("fc_heidenheim", "1. FC Heidenheim 1846"),
    208: OpenLigaDBTeamMapping("hallescher_fc", "Hallescher FC"),
    529: OpenLigaDBTeamMapping("sonnenhof_grossaspach", "SG Sonnenhof Großaspach"),
    553: OpenLigaDBTeamMapping("waldhof_mannheim", "SV Waldhof Mannheim"),
    1071: OpenLigaDBTeamMapping("eintracht_trier", "Eintracht Trier"),
    1635: OpenLigaDBTeamMapping("rb_leipzig", "RB Leipzig"),
    2199: OpenLigaDBTeamMapping("viktoria_koeln", "Viktoria Köln"),
    2499: OpenLigaDBTeamMapping("bahlinger_sc", "Bahlinger SC"),
    3078: OpenLigaDBTeamMapping("fc_saarbruecken", "1. FC Saarbrücken"),
    4550: OpenLigaDBTeamMapping("lueneburger_sk_hansa", "Lüneburger SK Hansa"),
    4555: OpenLigaDBTeamMapping("tsv_schott_mainz", "TSV Schott Mainz"),
    4568: OpenLigaDBTeamMapping("westfalia_rhynern", "SV Westfalia Rhynern"),
    4600: OpenLigaDBTeamMapping("vsg_altglienicke", "VSG Altglienicke Berlin"),
    4762: OpenLigaDBTeamMapping(
        "ssv_jeddeloh",
        "SSV Jeddeloh II",
        provider_name_aliases=("SSV Jeddeloh 2", "SSV Jeddeloh"),
    ),
    5276: OpenLigaDBTeamMapping("wuerzburger_kickers", "Würzburger Kickers"),
    5712: OpenLigaDBTeamMapping("sc_st_toenis", "SC St. Tönis"),
    6326: OpenLigaDBTeamMapping("phoenix_luebeck", "1. FC Phönix Lübeck"),
    6905: OpenLigaDBTeamMapping("sv_hemelingen", "SV Hemelingen"),
    7594: OpenLigaDBTeamMapping("vfb_krieschow", "VfB 1921 Krieschow"),
    7595: OpenLigaDBTeamMapping("hamburg_eimsbuetteler_bc", "Hamburg Eimsbütteler BC"),
}

SECOND_BUNDESLIGA_TEAM_MAPPINGS: dict[int, OpenLigaDBTeamMapping] = {
    36: OpenLigaDBTeamMapping("vfl_osnabrueck", "VfL Osnabrück"),
    54: OpenLigaDBTeamMapping("hertha_bsc", "Hertha BSC"),
    55: OpenLigaDBTeamMapping("hannover_96", "Hannover 96"),
    74: OpenLigaDBTeamMapping("eintracht_braunschweig", "Eintracht Braunschweig"),
    76: OpenLigaDBTeamMapping("fc_kaiserslautern", "1. FC Kaiserslautern"),
    78: OpenLigaDBTeamMapping("fc_magdeburg", "1. FC Magdeburg"),
    79: OpenLigaDBTeamMapping("fc_nuernberg", "1. FC Nürnberg"),
    83: OpenLigaDBTeamMapping("arminia_bielefeld", "DSC Arminia Bielefeld"),
    93: OpenLigaDBTeamMapping("energie_cottbus", "Energie Cottbus"),
    98: OpenLigaDBTeamMapping("fc_st_pauli", "FC St. Pauli"),
    104: OpenLigaDBTeamMapping("holstein_kiel", "Holstein Kiel"),
    105: OpenLigaDBTeamMapping("karlsruher_sc", "Karlsruher SC"),
    115: OpenLigaDBTeamMapping("greuther_fuerth", "SpVgg Greuther Fürth"),
    118: OpenLigaDBTeamMapping("sv_darmstadt_98", "SV Darmstadt 98"),
    129: OpenLigaDBTeamMapping("vfl_bochum", "VfL Bochum"),
    131: OpenLigaDBTeamMapping("vfl_wolfsburg", "VfL Wolfsburg"),
    177: OpenLigaDBTeamMapping("dynamo_dresden", "Dynamo Dresden"),
    199: OpenLigaDBTeamMapping("fc_heidenheim", "1. FC Heidenheim 1846"),
}

CHAMPIONS_LEAGUE_TEAM_MAPPINGS: dict[int, OpenLigaDBTeamMapping] = {
    7: OpenLigaDBTeamMapping("borussia_dortmund", "Borussia Dortmund"),
    16: OpenLigaDBTeamMapping("vfb_stuttgart", "VfB Stuttgart"),
    40: OpenLigaDBTeamMapping("fc_bayern_muenchen", "FC Bayern München"),
    356: OpenLigaDBTeamMapping("barcelona", "FC Barcelona"),
    366: OpenLigaDBTeamMapping("fenerbahce", "Fenerbahçe SK"),
    370: OpenLigaDBTeamMapping("liverpool", "FC Liverpool"),
    375: OpenLigaDBTeamMapping("porto", "FC Porto"),
    376: OpenLigaDBTeamMapping("psv_eindhoven", "PSV Eindhoven"),
    378: OpenLigaDBTeamMapping("roma", "AS Rom"),
    382: OpenLigaDBTeamMapping("villarreal", "Villarreal CF"),
    438: OpenLigaDBTeamMapping("aston_villa", "Aston Villa"),
    733: OpenLigaDBTeamMapping("inter_milan", "Inter Mailand"),
    1133: OpenLigaDBTeamMapping("real_madrid", "Real Madrid"),
    1186: OpenLigaDBTeamMapping("shakhtar_donetsk", "Shakhtar Donetsk"),
    1204: OpenLigaDBTeamMapping("lille", "Lille OSC"),
    1205: OpenLigaDBTeamMapping("sporting_cp", "Sporting CP"),
    1210: OpenLigaDBTeamMapping("club_brugge", "FC Brügge"),
    1217: OpenLigaDBTeamMapping("aek_athens", "AEK Athen"),
    1484: OpenLigaDBTeamMapping("viking", "Viking"),
    1635: OpenLigaDBTeamMapping("rb_leipzig", "RB Leipzig"),
    1770: OpenLigaDBTeamMapping("feyenoord", "Feyenoord Rotterdam"),
    1804: OpenLigaDBTeamMapping("real_betis", "Real Betis"),
    2281: OpenLigaDBTeamMapping("paris_saint_germain", "Paris St. Germain"),
    2331: OpenLigaDBTeamMapping("napoli", "SSC Napoli"),
    2554: OpenLigaDBTeamMapping("galatasaray", "Galatasaray Istanbul"),
    2556: OpenLigaDBTeamMapping("manchester_united", "Manchester United FC"),
    2617: OpenLigaDBTeamMapping("arsenal", "FC Arsenal"),
    4241: OpenLigaDBTeamMapping("atletico_madrid", "Atletico Madrid"),
    4244: OpenLigaDBTeamMapping("manchester_city", "Manchester City"),
    4578: OpenLigaDBTeamMapping("slavia_prague", "Slavia Prag"),
    5139: OpenLigaDBTeamMapping("lask", "LASK"),
    5699: OpenLigaDBTeamMapping("slovan_bratislava", "Slovan Bratislava"),
    5707: OpenLigaDBTeamMapping("bodo_glimt", "FK Bodö/Glimt"),
    5962: OpenLigaDBTeamMapping("lens", "RC Lens"),
    8787: OpenLigaDBTeamMapping("como", "Como 1907"),
    8798: OpenLigaDBTeamMapping("sabah", "Sabah"),
}

# Country names are independently reviewed against UEFA's published League A
# groups. Provider IDs are deliberately learned into the private source-mapping
# repository on first import instead of being copied into the source tree.
NATIONS_LEAGUE_A_TEAM_MAPPINGS_BY_NAME: dict[str, str] = {
    "Belgien": "belgium",
    "Dänemark": "denmark",
    "Deutschland": "germany",
    "England": "england_national_team",
    "Frankreich": "france",
    "Griechenland": "greece",
    "Italien": "italy",
    "Kroatien": "croatia",
    "Niederlande": "netherlands",
    "Norwegen": "norway",
    "Portugal": "portugal",
    "Serbien": "serbia",
    "Spanien": "spain",
    "Tschechien": "czechia",
    "Türkei": "turkiye",
    "Wales": "wales_national_team",
}

TEAM_MAPPINGS_BY_COMPETITION_KEY = {
    "uefa_champions_league": CHAMPIONS_LEAGUE_TEAM_MAPPINGS,
    "dfb_pokal": DFB_POKAL_TEAM_MAPPINGS,
    "second_bundesliga": SECOND_BUNDESLIGA_TEAM_MAPPINGS,
}


def resolve_team_key(
    competition_key: str, provider_id: int, provider_name: str
) -> str | None:
    if competition_key == "uefa_nations_league":
        return NATIONS_LEAGUE_A_TEAM_MAPPINGS_BY_NAME.get(provider_name.strip())
    mapping = TEAM_MAPPINGS_BY_COMPETITION_KEY.get(competition_key, {}).get(provider_id)
    if mapping is None or not mapping.accepts_provider_name(provider_name):
        return None
    return mapping.participant_key


def get_reviewed_team_keys(competition_key: str) -> frozenset[str]:
    if competition_key == "uefa_nations_league":
        return frozenset(NATIONS_LEAGUE_A_TEAM_MAPPINGS_BY_NAME.values())
    return frozenset(
        mapping.participant_key
        for mapping in TEAM_MAPPINGS_BY_COMPETITION_KEY.get(
            competition_key, {}
        ).values()
    )
