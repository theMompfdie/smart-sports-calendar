from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class OefbIcalTeamMapping:
    participant_key: str
    provider_name: str


OEFB_CUP_TEAM_MAPPINGS: Mapping[int, OefbIcalTeamMapping] = MappingProxyType(
    {
        1027: OefbIcalTeamMapping("wiener_viktoria", "Wiener Viktoria"),
        1031: OefbIcalTeamMapping("fac_wien", "FAC Wien"),
        1040: OefbIcalTeamMapping("fk_austria_wien", "FK Austria Wien"),
        1076: OefbIcalTeamMapping("sv_wienerberg_1921", "SV Wienerberg 1921"),
        1097: OefbIcalTeamMapping("sk_rapid", "SK Rapid"),
        1112: OefbIcalTeamMapping("wiener_sport_club", "Wiener Sport-Club"),
        1119: OefbIcalTeamMapping("first_vienna_fc_1894", "First Vienna FC 1894"),
        1135: OefbIcalTeamMapping("sr_donaufeld", "SR Donaufeld"),
        2092: OefbIcalTeamMapping("sv_leobendorf", "SV Leobendorf"),
        2201: OefbIcalTeamMapping("admira_wacker", "Admira Wacker"),
        2238: OefbIcalTeamMapping("fcm_traiskirchen", "FCM Traiskirchen"),
        2293: OefbIcalTeamMapping("scheiblingkirchen_warth", "Scheiblingkirchen-Warth"),
        2359: OefbIcalTeamMapping("wieselburg", "Wieselburg"),
        2441: OefbIcalTeamMapping(
            "spg_krems_sc_getzersdorf", "SPG Krems SC / Getzersdorf KM"
        ),
        2461: OefbIcalTeamMapping("sv_horn", "SV Horn"),
        2610: OefbIcalTeamMapping("sku_amstetten", "SKU Ertl Glas Amstetten"),
        2622: OefbIcalTeamMapping("skn_st_poelten", "SKN St. Pölten"),
        3055: OefbIcalTeamMapping("scr_altach", "SCR Altach"),
        3056: OefbIcalTeamMapping("vfb_hohenems", "VfB Hohenems"),
        3068: OefbIcalTeamMapping("fc_lustenau_1907", "FC Lustenau 1907"),
        3076: OefbIcalTeamMapping("fc_lauterach", "intemann FC Lauterach"),
        3090: OefbIcalTeamMapping("fc_dornbirn_1913", "FC Dornbirn 1913"),
        3094: OefbIcalTeamMapping("sc_austria_lustenau", "SC Austria Lustenau"),
        3101: OefbIcalTeamMapping("sw_bregenz", "SW Bregenz"),
        4035: OefbIcalTeamMapping("lask", "LASK"),
        4052: OefbIcalTeamMapping("fc_blau_weiss_linz", "FC Blau Weiss Linz"),
        4124: OefbIcalTeamMapping(
            "spg_bad_leonfelden_schenkenfelden",
            "SPG VORTUNA Bad Leonfelden/Schenkenfelden",
        ),
        4186: OefbIcalTeamMapping("sk_vorwaerts_steyr", "SK Vorwärts Steyr"),
        4193: OefbIcalTeamMapping("union_dietach", "Union PROCON Dietach"),
        4242: OefbIcalTeamMapping("fc_hertha_wels", "FC Hertha Wels"),
        4281: OefbIcalTeamMapping(
            "spg_wallern_st_marienkirchen", "SPG Wallern / St. Marienk./P KM"
        ),
        4373: OefbIcalTeamMapping("sv_ried", "SV Oberbank Ried"),
        4381: OefbIcalTeamMapping("union_gurten", "Gurten"),
        5012: OefbIcalTeamMapping("sk_bischofshofen", "Bischofshofen Sportklub 1933"),
        5032: OefbIcalTeamMapping("sv_wals_gruenau", "SV Wals-Grünau"),
        5045: OefbIcalTeamMapping("sv_kuchl", "SV Kuchl"),
        5075: OefbIcalTeamMapping("fc_red_bull_salzburg", "FC Red Bull Salzburg"),
        5105: OefbIcalTeamMapping("sv_seekirchen", "SV teampool Seekirchen"),
        5134: OefbIcalTeamMapping("sv_austria_salzburg", "SV Austria Salzburg"),
        6003: OefbIcalTeamMapping("sc_schwaz", "SC EGLO Schwaz"),
        6020: OefbIcalTeamMapping("sc_imst", "SC Imst"),
        6041: OefbIcalTeamMapping("fc_kitzbuehel", "FC Powerspine Kitzbühel"),
        6105: OefbIcalTeamMapping("svg_reichenau", "SVG Reichenau"),
        6117: OefbIcalTeamMapping("wsg_tirol", "WSG Tirol"),
        6159: OefbIcalTeamMapping("fc_wacker_innsbruck", "FC Wacker Innsbruck"),
        7037: OefbIcalTeamMapping("sv_leithaprodersdorf", "SV Leithaprodersdorf"),
        7071: OefbIcalTeamMapping("sc_esv_parndorf_1919", "SC/ESV Parndorf 1919"),
        7114: OefbIcalTeamMapping("sv_oberwart", "SV Klöcher Bau Oberwart"),
        7504: OefbIcalTeamMapping(
            "mattersburger_sv_2020", "Mattersburger Sportverein 2020"
        ),
        8015: OefbIcalTeamMapping("sk_sturm_graz", "SK Puntigamer Sturm Graz"),
        8029: OefbIcalTeamMapping("grazer_ak_1902", "Grazer AK 1902"),
        8142: OefbIcalTeamMapping("tsv_hartberg", "TSV Egger Glas Hartberg"),
        8145: OefbIcalTeamMapping("sv_lafnitz", "Lafnitz"),
        8192: OefbIcalTeamMapping("sc_kalsdorf", "Kalsdorf"),
        8244: OefbIcalTeamMapping("deutschlandsberger_sc", "Deutschlandsberg"),
        8256: OefbIcalTeamMapping("ask_voitsberg", "Voitsberg"),
        8293: OefbIcalTeamMapping("dsv_leoben", "DSV Leoben"),
        8411: OefbIcalTeamMapping("ksv_1919", "KSV 1919"),
        8414: OefbIcalTeamMapping(
            "sv_tillmitsch", "SV Fleischereimaschinen Schenk Tillmitsch"
        ),
        9068: OefbIcalTeamMapping("svg_bleiburg", "Bleiburg"),
        9080: OefbIcalTeamMapping("sv_velden", "Velden"),
        9091: OefbIcalTeamMapping("sk_treibach", "Treibach"),
        9109: OefbIcalTeamMapping("sk_austria_klagenfurt", "Austria Klagenfurt"),
        9110: OefbIcalTeamMapping("wolfsberger_ac", "RZ Pellets WAC"),
    }
)


def resolve_team_key(
    provider_id: int,
    mappings: Mapping[int, OefbIcalTeamMapping] = OEFB_CUP_TEAM_MAPPINGS,
) -> str | None:
    mapping = mappings.get(provider_id)
    return None if mapping is None else mapping.participant_key
