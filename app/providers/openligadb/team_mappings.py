from dataclasses import dataclass


@dataclass(frozen=True)
class OpenLigaDBTeamMapping:
    participant_key: str
    provider_name: str


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
    3078: OpenLigaDBTeamMapping("fc_saarbruecken", "1.FC Saarbrücken"),
    4550: OpenLigaDBTeamMapping("lueneburger_sk_hansa", "Lüneburger SK Hansa"),
    4555: OpenLigaDBTeamMapping("tsv_schott_mainz", "TSV Schott Mainz"),
    4568: OpenLigaDBTeamMapping("westfalia_rhynern", "SV Westfalia Rhynern"),
    4600: OpenLigaDBTeamMapping("vsg_altglienicke", "VSG Altglienicke Berlin"),
    4762: OpenLigaDBTeamMapping("ssv_jeddeloh", "SSV Jeddeloh 2"),
    5276: OpenLigaDBTeamMapping("wuerzburger_kickers", "Würzburger Kickers"),
    5712: OpenLigaDBTeamMapping("sc_st_toenis", "SC St. Tönis"),
    6326: OpenLigaDBTeamMapping("phoenix_luebeck", "1. FC Phönix Lübeck"),
    6905: OpenLigaDBTeamMapping("sv_hemelingen", "SV Hemelingen"),
    7594: OpenLigaDBTeamMapping("vfb_krieschow", "VfB 1921 Krieschow"),
    7595: OpenLigaDBTeamMapping("hamburg_eimsbuetteler_bc", "Hamburg Eimsbütteler BC"),
}


def resolve_team_key(provider_id: int, provider_name: str) -> str | None:
    mapping = DFB_POKAL_TEAM_MAPPINGS.get(provider_id)
    if mapping is None or mapping.provider_name != provider_name.strip():
        return None
    return mapping.participant_key


def get_reviewed_team_keys() -> frozenset[str]:
    return frozenset(
        mapping.participant_key for mapping in DFB_POKAL_TEAM_MAPPINGS.values()
    )
