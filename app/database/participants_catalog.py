from dataclasses import dataclass

from app.database.competitions_repository import CompetitionsRepository
from app.database.participants_repository import Participant, ParticipantsRepository
from app.database.season_participants_repository import (
    SeasonParticipant,
    SeasonParticipantsRepository,
)
from app.database.seasons_repository import SeasonsRepository
from app.database.sports_repository import SportsRepository


@dataclass(frozen=True)
class ParticipantsCatalogResult:
    participants: list[Participant]
    season_participants: list[SeasonParticipant]


@dataclass(frozen=True)
class ParticipantCatalogEntry:
    participant_key: str
    name: str
    short_name: str
    country_code: str | None = None


@dataclass(frozen=True)
class SeasonParticipantsCatalogEntry:
    sport_key: str
    competition_key: str
    season_key: str
    country_code: str
    participants: tuple[ParticipantCatalogEntry, ...]


PREMIER_LEAGUE_2026_27_TEAMS = (
    ("arsenal", "Arsenal", "Arsenal"),
    ("aston_villa", "Aston Villa", "Aston Villa"),
    ("bournemouth", "AFC Bournemouth", "Bournemouth"),
    ("brentford", "Brentford", "Brentford"),
    ("brighton_and_hove_albion", "Brighton & Hove Albion", "Brighton"),
    ("chelsea", "Chelsea", "Chelsea"),
    ("coventry_city", "Coventry City", "Coventry"),
    ("crystal_palace", "Crystal Palace", "Crystal Palace"),
    ("everton", "Everton", "Everton"),
    ("fulham", "Fulham", "Fulham"),
    ("hull_city", "Hull City", "Hull"),
    ("ipswich_town", "Ipswich Town", "Ipswich"),
    ("leeds_united", "Leeds United", "Leeds"),
    ("liverpool", "Liverpool", "Liverpool"),
    ("manchester_city", "Manchester City", "Man City"),
    ("manchester_united", "Manchester United", "Man Utd"),
    ("newcastle_united", "Newcastle United", "Newcastle"),
    ("nottingham_forest", "Nottingham Forest", "Nott'm Forest"),
    ("sunderland", "Sunderland", "Sunderland"),
    ("tottenham_hotspur", "Tottenham Hotspur", "Spurs"),
)

BUNDESLIGA_2026_27_TEAMS = (
    ("fc_koeln", "1. FC Köln", "1. FC Köln"),
    ("fc_union_berlin", "1. FC Union Berlin", "Union Berlin"),
    ("fsv_mainz_05", "1. FSV Mainz 05", "Mainz"),
    ("bayer_04_leverkusen", "Bayer 04 Leverkusen", "Leverkusen"),
    ("borussia_dortmund", "Borussia Dortmund", "Dortmund"),
    (
        "borussia_moenchengladbach",
        "Borussia Mönchengladbach",
        "M'gladbach",
    ),
    ("eintracht_frankfurt", "Eintracht Frankfurt", "Frankfurt"),
    ("fc_augsburg", "FC Augsburg", "Augsburg"),
    ("fc_bayern_muenchen", "FC Bayern München", "Bayern"),
    ("fc_schalke_04", "FC Schalke 04", "Schalke"),
    ("hamburger_sv", "Hamburger SV", "HSV"),
    ("rb_leipzig", "RB Leipzig", "RB Leipzig"),
    ("sc_freiburg", "SC Freiburg", "Freiburg"),
    ("sc_paderborn_07", "SC Paderborn 07", "SC Paderborn"),
    ("sv_elversberg", "SV 07 Elversberg", "Elversberg"),
    ("werder_bremen", "SV Werder Bremen", "Bremen"),
    ("tsg_hoffenheim", "TSG 1899 Hoffenheim", "Hoffenheim"),
    ("vfb_stuttgart", "VfB Stuttgart", "Stuttgart"),
)

CHAMPIONSHIP_2026_27_TEAMS = (
    ("birmingham_city", "Birmingham City", "Birmingham", "GB-ENG"),
    ("blackburn_rovers", "Blackburn Rovers", "Blackburn", "GB-ENG"),
    ("bolton_wanderers", "Bolton Wanderers", "Bolton", "GB-ENG"),
    ("bristol_city", "Bristol City", "Bristol City", "GB-ENG"),
    ("burnley", "Burnley", "Burnley", "GB-ENG"),
    ("cardiff_city", "Cardiff City", "Cardiff", "GB-WLS"),
    ("charlton_athletic", "Charlton Athletic", "Charlton", "GB-ENG"),
    ("derby_county", "Derby County", "Derby County", "GB-ENG"),
    ("lincoln_city", "Lincoln City", "Lincoln City", "GB-ENG"),
    ("middlesbrough", "Middlesbrough", "Middlesbrough", "GB-ENG"),
    ("millwall", "Millwall", "Millwall", "GB-ENG"),
    ("norwich_city", "Norwich City", "Norwich", "GB-ENG"),
    ("portsmouth", "Portsmouth", "Portsmouth", "GB-ENG"),
    ("preston_north_end", "Preston North End", "Preston NE", "GB-ENG"),
    ("queens_park_rangers", "Queens Park Rangers", "QPR", "GB-ENG"),
    ("sheffield_united", "Sheffield United", "Sheffield Utd", "GB-ENG"),
    ("southampton", "Southampton", "Southampton", "GB-ENG"),
    ("stoke_city", "Stoke City", "Stoke", "GB-ENG"),
    ("swansea_city", "Swansea City", "Swansea", "GB-WLS"),
    ("watford", "Watford", "Watford", "GB-ENG"),
    ("west_bromwich_albion", "West Bromwich Albion", "West Brom", "GB-ENG"),
    ("west_ham_united", "West Ham United", "West Ham", "GB-ENG"),
    (
        "wolverhampton_wanderers",
        "Wolverhampton Wanderers",
        "Wolverhampton",
        "GB-ENG",
    ),
    ("wrexham", "Wrexham", "Wrexham", "GB-WLS"),
)

EFL_CUP_2026_27_TEAMS = (
    ("afc_wimbledon", "AFC Wimbledon", "AFC Wimbledon", "GB-ENG"),
    ("accrington_stanley", "Accrington Stanley", "Accrington Stanley", "GB-ENG"),
    ("arsenal", "Arsenal", "Arsenal", "GB-ENG"),
    ("aston_villa", "Aston Villa", "Aston Villa", "GB-ENG"),
    ("barnet", "Barnet", "Barnet", "GB-ENG"),
    ("barnsley", "Barnsley", "Barnsley", "GB-ENG"),
    ("birmingham_city", "Birmingham City", "Birmingham", "GB-ENG"),
    ("blackburn_rovers", "Blackburn Rovers", "Blackburn", "GB-ENG"),
    ("blackpool", "Blackpool", "Blackpool", "GB-ENG"),
    ("bolton_wanderers", "Bolton Wanderers", "Bolton", "GB-ENG"),
    ("bournemouth", "AFC Bournemouth", "Bournemouth", "GB-ENG"),
    ("bradford_city", "Bradford City", "Bradford City", "GB-ENG"),
    ("brentford", "Brentford", "Brentford", "GB-ENG"),
    ("brighton_and_hove_albion", "Brighton & Hove Albion", "Brighton", "GB-ENG"),
    ("bristol_city", "Bristol City", "Bristol City", "GB-ENG"),
    ("bristol_rovers", "Bristol Rovers", "Bristol Rovers", "GB-ENG"),
    ("bromley", "Bromley", "Bromley", "GB-ENG"),
    ("burnley", "Burnley", "Burnley", "GB-ENG"),
    ("burton_albion", "Burton Albion", "Burton Albion", "GB-ENG"),
    ("cambridge_united", "Cambridge United", "Cambridge United", "GB-ENG"),
    ("cardiff_city", "Cardiff City", "Cardiff", "GB-WLS"),
    ("charlton_athletic", "Charlton Athletic", "Charlton", "GB-ENG"),
    ("chelsea", "Chelsea", "Chelsea", "GB-ENG"),
    ("cheltenham_town", "Cheltenham Town", "Cheltenham Town", "GB-ENG"),
    ("chesterfield", "Chesterfield", "Chesterfield", "GB-ENG"),
    ("colchester_united", "Colchester United", "Colchester United", "GB-ENG"),
    ("coventry_city", "Coventry City", "Coventry", "GB-ENG"),
    ("crawley_town", "Crawley Town", "Crawley Town", "GB-ENG"),
    ("crewe_alexandra", "Crewe Alexandra", "Crewe Alexandra", "GB-ENG"),
    ("crystal_palace", "Crystal Palace", "Crystal Palace", "GB-ENG"),
    ("derby_county", "Derby County", "Derby County", "GB-ENG"),
    ("doncaster_rovers", "Doncaster Rovers", "Doncaster Rovers", "GB-ENG"),
    ("everton", "Everton", "Everton", "GB-ENG"),
    ("exeter_city", "Exeter City", "Exeter City", "GB-ENG"),
    ("fleetwood_town", "Fleetwood Town", "Fleetwood Town", "GB-ENG"),
    ("fulham", "Fulham", "Fulham", "GB-ENG"),
    ("gillingham", "Gillingham", "Gillingham", "GB-ENG"),
    ("grimsby_town", "Grimsby Town", "Grimsby Town", "GB-ENG"),
    ("huddersfield_town", "Huddersfield Town", "Huddersfield Town", "GB-ENG"),
    ("hull_city", "Hull City", "Hull", "GB-ENG"),
    ("ipswich_town", "Ipswich Town", "Ipswich", "GB-ENG"),
    ("leeds_united", "Leeds United", "Leeds", "GB-ENG"),
    ("leicester_city", "Leicester City", "Leicester City", "GB-ENG"),
    ("leyton_orient", "Leyton Orient", "Leyton Orient", "GB-ENG"),
    ("lincoln_city", "Lincoln City", "Lincoln City", "GB-ENG"),
    ("liverpool", "Liverpool", "Liverpool", "GB-ENG"),
    ("luton_town", "Luton Town", "Luton Town", "GB-ENG"),
    ("manchester_city", "Manchester City", "Man City", "GB-ENG"),
    ("manchester_united", "Manchester United", "Man Utd", "GB-ENG"),
    ("mansfield_town", "Mansfield Town", "Mansfield Town", "GB-ENG"),
    ("middlesbrough", "Middlesbrough", "Middlesbrough", "GB-ENG"),
    ("millwall", "Millwall", "Millwall", "GB-ENG"),
    ("milton_keynes_dons", "Milton Keynes Dons", "Milton Keynes Dons", "GB-ENG"),
    ("newcastle_united", "Newcastle United", "Newcastle", "GB-ENG"),
    ("newport_county", "Newport County", "Newport County", "GB-WLS"),
    ("northampton_town", "Northampton Town", "Northampton Town", "GB-ENG"),
    ("norwich_city", "Norwich City", "Norwich", "GB-ENG"),
    ("nottingham_forest", "Nottingham Forest", "Nott'm Forest", "GB-ENG"),
    ("notts_county", "Notts County", "Notts County", "GB-ENG"),
    ("oldham_athletic", "Oldham Athletic", "Oldham Athletic", "GB-ENG"),
    ("oxford_united", "Oxford United", "Oxford United", "GB-ENG"),
    ("peterborough_united", "Peterborough United", "Peterborough United", "GB-ENG"),
    ("plymouth_argyle", "Plymouth Argyle", "Plymouth Argyle", "GB-ENG"),
    ("port_vale", "Port Vale", "Port Vale", "GB-ENG"),
    ("portsmouth", "Portsmouth", "Portsmouth", "GB-ENG"),
    ("preston_north_end", "Preston North End", "Preston NE", "GB-ENG"),
    ("queens_park_rangers", "Queens Park Rangers", "QPR", "GB-ENG"),
    ("reading", "Reading", "Reading", "GB-ENG"),
    ("rochdale", "Rochdale", "Rochdale", "GB-ENG"),
    ("rotherham_united", "Rotherham United", "Rotherham United", "GB-ENG"),
    ("salford_city", "Salford City", "Salford City", "GB-ENG"),
    ("sheffield_united", "Sheffield United", "Sheffield Utd", "GB-ENG"),
    ("sheffield_wednesday", "Sheffield Wednesday", "Sheffield Wednesday", "GB-ENG"),
    ("shrewsbury_town", "Shrewsbury Town", "Shrewsbury Town", "GB-ENG"),
    ("southampton", "Southampton", "Southampton", "GB-ENG"),
    ("stevenage", "Stevenage", "Stevenage", "GB-ENG"),
    ("stockport_county", "Stockport County", "Stockport County", "GB-ENG"),
    ("stoke_city", "Stoke City", "Stoke", "GB-ENG"),
    ("sunderland", "Sunderland", "Sunderland", "GB-ENG"),
    ("swansea_city", "Swansea City", "Swansea", "GB-WLS"),
    ("swindon_town", "Swindon Town", "Swindon Town", "GB-ENG"),
    ("tottenham_hotspur", "Tottenham Hotspur", "Spurs", "GB-ENG"),
    ("tranmere_rovers", "Tranmere Rovers", "Tranmere Rovers", "GB-ENG"),
    ("walsall", "Walsall", "Walsall", "GB-ENG"),
    ("watford", "Watford", "Watford", "GB-ENG"),
    ("west_bromwich_albion", "West Bromwich Albion", "West Brom", "GB-ENG"),
    ("west_ham_united", "West Ham United", "West Ham", "GB-ENG"),
    ("wigan_athletic", "Wigan Athletic", "Wigan Athletic", "GB-ENG"),
    ("wolverhampton_wanderers", "Wolverhampton Wanderers", "Wolverhampton", "GB-ENG"),
    ("wrexham", "Wrexham", "Wrexham", "GB-WLS"),
    ("wycombe_wanderers", "Wycombe Wanderers", "Wycombe Wanderers", "GB-ENG"),
    ("york_city", "York City", "York City", "GB-ENG"),
)

SECOND_BUNDESLIGA_2026_27_TEAMS = (
    ("vfl_osnabrueck", "VfL Osnabrück", "Osnabrück"),
    ("hertha_bsc", "Hertha BSC", "Hertha"),
    ("hannover_96", "Hannover 96", "Hannover"),
    ("eintracht_braunschweig", "Eintracht Braunschweig", "Braunschweig"),
    ("fc_kaiserslautern", "1. FC Kaiserslautern", "Kaiserslautern"),
    ("fc_magdeburg", "1. FC Magdeburg", "Magdeburg"),
    ("fc_nuernberg", "1. FC Nürnberg", "Nürnberg"),
    ("arminia_bielefeld", "DSC Arminia Bielefeld", "Bielefeld"),
    ("energie_cottbus", "Energie Cottbus", "Cottbus"),
    ("fc_st_pauli", "FC St. Pauli", "St. Pauli"),
    ("holstein_kiel", "Holstein Kiel", "Kiel"),
    ("karlsruher_sc", "Karlsruher SC", "Karlsruhe"),
    ("greuther_fuerth", "SpVgg Greuther Fürth", "Fürth"),
    ("sv_darmstadt_98", "SV Darmstadt 98", "Darmstadt"),
    ("vfl_bochum", "VfL Bochum", "Bochum"),
    ("vfl_wolfsburg", "VfL Wolfsburg", "Wolfsburg"),
    ("dynamo_dresden", "Dynamo Dresden", "Dresden"),
    ("fc_heidenheim", "1. FC Heidenheim 1846", "Heidenheim"),
)

DFB_POKAL_2026_27_TEAMS = (
    ("bayer_04_leverkusen", "Bayer 04 Leverkusen", "Leverkusen"),
    ("borussia_dortmund", "Borussia Dortmund", "Dortmund"),
    ("fc_schalke_04", "FC Schalke 04", "Schalke"),
    ("vfb_stuttgart", "VfB Stuttgart", "Stuttgart"),
    ("sc_paderborn_07", "SC Paderborn 07", "SC Paderborn"),
    ("vfl_osnabrueck", "VfL Osnabrück", "Osnabrück"),
    ("fc_bayern_muenchen", "FC Bayern München", "Bayern"),
    ("hertha_bsc", "Hertha BSC", "Hertha"),
    ("hannover_96", "Hannover 96", "Hannover"),
    ("fc_koeln", "1. FC Köln", "1. FC Köln"),
    ("erzgebirge_aue", "Erzgebirge Aue", "Aue"),
    ("carl_zeiss_jena", "FC Carl Zeiss Jena", "Jena"),
    ("eintracht_braunschweig", "Eintracht Braunschweig", "Braunschweig"),
    ("fc_kaiserslautern", "1. FC Kaiserslautern", "Kaiserslautern"),
    ("fc_magdeburg", "1. FC Magdeburg", "Magdeburg"),
    ("fc_nuernberg", "1. FC Nürnberg", "Nürnberg"),
    ("fc_union_berlin", "1. FC Union Berlin", "Union Berlin"),
    ("fsv_mainz_05", "1. FSV Mainz 05", "Mainz"),
    ("arminia_bielefeld", "DSC Arminia Bielefeld", "Bielefeld"),
    (
        "borussia_moenchengladbach",
        "Borussia Mönchengladbach",
        "M'gladbach",
    ),
    ("eintracht_frankfurt", "Eintracht Frankfurt", "Frankfurt"),
    ("energie_cottbus", "Energie Cottbus", "Cottbus"),
    ("fc_augsburg", "FC Augsburg", "Augsburg"),
    ("fc_st_pauli", "FC St. Pauli", "St. Pauli"),
    ("hamburger_sv", "Hamburger SV", "HSV"),
    ("hansa_rostock", "Hansa Rostock", "Rostock"),
    ("holstein_kiel", "Holstein Kiel", "Kiel"),
    ("karlsruher_sc", "Karlsruher SC", "Karlsruhe"),
    ("msv_duisburg", "MSV Duisburg", "Duisburg"),
    ("rot_weiss_essen", "Rot-Weiss Essen", "Rot-Weiss Essen"),
    ("sc_freiburg", "SC Freiburg", "Freiburg"),
    ("sc_verl", "SC Verl", "Verl"),
    ("greuther_fuerth", "SpVgg Greuther Fürth", "Fürth"),
    ("sv_darmstadt_98", "SV Darmstadt 98", "Darmstadt"),
    ("tsv_1860_muenchen", "TSV 1860 München", "1860 München"),
    ("vfl_bochum", "VfL Bochum", "Bochum"),
    ("vfl_wolfsburg", "VfL Wolfsburg", "Wolfsburg"),
    ("werder_bremen", "SV Werder Bremen", "Bremen"),
    ("wehen_wiesbaden", "SV Wehen Wiesbaden", "Wiesbaden"),
    ("tsg_hoffenheim", "TSG 1899 Hoffenheim", "Hoffenheim"),
    ("dynamo_dresden", "Dynamo Dresden", "Dresden"),
    ("fortuna_duesseldorf", "Fortuna Düsseldorf", "Düsseldorf"),
    ("preussen_muenster", "Preußen Münster", "Münster"),
    ("sv_elversberg", "SV 07 Elversberg", "Elversberg"),
    ("fc_heidenheim", "1. FC Heidenheim 1846", "Heidenheim"),
    ("hallescher_fc", "Hallescher FC", "Halle"),
    ("sonnenhof_grossaspach", "SG Sonnenhof Großaspach", "Großaspach"),
    ("waldhof_mannheim", "SV Waldhof Mannheim", "Mannheim"),
    ("eintracht_trier", "Eintracht Trier", "Trier"),
    ("rb_leipzig", "RB Leipzig", "RB Leipzig"),
    ("viktoria_koeln", "Viktoria Köln", "Viktoria Köln"),
    ("bahlinger_sc", "Bahlinger SC", "Bahlinger SC"),
    ("fc_saarbruecken", "1. FC Saarbrücken", "Saarbrücken"),
    ("lueneburger_sk_hansa", "Lüneburger SK Hansa", "LSK"),
    ("tsv_schott_mainz", "TSV Schott Mainz", "SCHOTT"),
    ("westfalia_rhynern", "SV Westfalia Rhynern", "Rhynern"),
    ("vsg_altglienicke", "VSG Altglienicke Berlin", "Altglienicke"),
    ("ssv_jeddeloh", "SSV Jeddeloh 2", "SSV Jeddeloh"),
    ("wuerzburger_kickers", "Würzburger Kickers", "Würzburg"),
    ("sc_st_toenis", "SC St. Tönis", "St. Tönis"),
    ("phoenix_luebeck", "1. FC Phönix Lübeck", "Phönix Lübeck"),
    ("sv_hemelingen", "SV Hemelingen", "Hemelingen"),
    ("vfb_krieschow", "VfB 1921 Krieschow", "Krieschow"),
    ("hamburg_eimsbuetteler_bc", "Hamburg Eimsbütteler BC", "HEBC"),
)

OEFB_CUP_2026_27_TEAMS = (
    ("wiener_viktoria", "Wiener Viktoria", "Wiener Viktoria"),
    ("fac_wien", "FAC Wien", "FAC Wien"),
    ("fk_austria_wien", "FK Austria Wien", "Austria Wien"),
    ("sv_wienerberg_1921", "SV Wienerberg 1921", "SV Wienerberg"),
    ("sk_rapid", "SK Rapid", "SK Rapid"),
    ("wiener_sport_club", "Wiener Sport-Club", "Wiener Sport-Club"),
    ("first_vienna_fc_1894", "First Vienna FC 1894", "First Vienna"),
    ("sr_donaufeld", "SR Donaufeld", "SR Donaufeld"),
    ("sv_leobendorf", "SV Leobendorf", "SV Leobendorf"),
    ("admira_wacker", "Admira Wacker", "Admira Wacker"),
    ("fcm_traiskirchen", "FCM Traiskirchen", "Traiskirchen"),
    (
        "scheiblingkirchen_warth",
        "Scheiblingkirchen-Warth",
        "Scheiblingkirchen-Warth",
    ),
    ("wieselburg", "Wieselburg", "Wieselburg"),
    (
        "spg_krems_sc_getzersdorf",
        "SPG Krems SC / Getzersdorf KM",
        "SPG Krems/Getzersdorf",
    ),
    ("sv_horn", "SV Horn", "SV Horn"),
    ("sku_amstetten", "SKU Ertl Glas Amstetten", "SKU Amstetten"),
    ("skn_st_poelten", "SKN St. Pölten", "SKN St. Pölten"),
    ("scr_altach", "SCR Altach", "SCR Altach"),
    ("vfb_hohenems", "VfB Hohenems", "VfB Hohenems"),
    ("fc_lustenau_1907", "FC Lustenau 1907", "FC Lustenau"),
    ("fc_lauterach", "intemann FC Lauterach", "FC Lauterach"),
    ("fc_dornbirn_1913", "FC Dornbirn 1913", "FC Dornbirn"),
    ("sc_austria_lustenau", "SC Austria Lustenau", "Austria Lustenau"),
    ("sw_bregenz", "SW Bregenz", "SW Bregenz"),
    ("lask", "LASK", "LASK"),
    ("fc_blau_weiss_linz", "FC Blau Weiss Linz", "Blau-Weiss Linz"),
    (
        "spg_bad_leonfelden_schenkenfelden",
        "SPG VORTUNA Bad Leonfelden/Schenkenfelden",
        "SPG Bad Leonfelden/Schenkenfelden",
    ),
    ("sk_vorwaerts_steyr", "SK Vorwärts Steyr", "Vorwärts Steyr"),
    ("union_dietach", "Union PROCON Dietach", "Union Dietach"),
    ("fc_hertha_wels", "FC Hertha Wels", "Hertha Wels"),
    (
        "spg_wallern_st_marienkirchen",
        "SPG Wallern / St. Marienk./P KM",
        "SPG Wallern/St. Marienkirchen",
    ),
    ("sv_ried", "SV Oberbank Ried", "SV Ried"),
    ("union_gurten", "Gurten", "Gurten"),
    (
        "sk_bischofshofen",
        "Bischofshofen Sportklub 1933",
        "SK Bischofshofen",
    ),
    ("sv_wals_gruenau", "SV Wals-Grünau", "SV Wals-Grünau"),
    ("sv_kuchl", "SV Kuchl", "SV Kuchl"),
    ("fc_red_bull_salzburg", "FC Red Bull Salzburg", "Salzburg"),
    ("sv_seekirchen", "SV teampool Seekirchen", "SV Seekirchen"),
    ("sv_austria_salzburg", "SV Austria Salzburg", "Austria Salzburg"),
    ("sc_schwaz", "SC EGLO Schwaz", "SC Schwaz"),
    ("sc_imst", "SC Imst", "SC Imst"),
    ("fc_kitzbuehel", "FC Powerspine Kitzbühel", "FC Kitzbühel"),
    ("svg_reichenau", "SVG Reichenau", "SVG Reichenau"),
    ("wsg_tirol", "WSG Tirol", "WSG Tirol"),
    ("fc_wacker_innsbruck", "FC Wacker Innsbruck", "Wacker Innsbruck"),
    (
        "sv_leithaprodersdorf",
        "SV Leithaprodersdorf",
        "SV Leithaprodersdorf",
    ),
    ("sc_esv_parndorf_1919", "SC/ESV Parndorf 1919", "Parndorf"),
    ("sv_oberwart", "SV Klöcher Bau Oberwart", "SV Oberwart"),
    (
        "mattersburger_sv_2020",
        "Mattersburger Sportverein 2020",
        "Mattersburger SV",
    ),
    ("sk_sturm_graz", "SK Puntigamer Sturm Graz", "Sturm Graz"),
    ("grazer_ak_1902", "Grazer AK 1902", "Grazer AK"),
    ("tsv_hartberg", "TSV Egger Glas Hartberg", "TSV Hartberg"),
    ("sv_lafnitz", "Lafnitz", "Lafnitz"),
    ("sc_kalsdorf", "Kalsdorf", "Kalsdorf"),
    ("deutschlandsberger_sc", "Deutschlandsberg", "Deutschlandsberg"),
    ("ask_voitsberg", "Voitsberg", "Voitsberg"),
    ("dsv_leoben", "DSV Leoben", "DSV Leoben"),
    ("ksv_1919", "KSV 1919", "KSV 1919"),
    (
        "sv_tillmitsch",
        "SV Fleischereimaschinen Schenk Tillmitsch",
        "SV Tillmitsch",
    ),
    ("svg_bleiburg", "Bleiburg", "Bleiburg"),
    ("sv_velden", "Velden", "Velden"),
    ("sk_treibach", "Treibach", "Treibach"),
    ("sk_austria_klagenfurt", "Austria Klagenfurt", "Austria Klagenfurt"),
    ("wolfsberger_ac", "RZ Pellets WAC", "Wolfsberger AC"),
)

AUSTRIAN_BUNDESLIGA_2026_27_TEAMS = (
    ("lask", "LASK", "LASK"),
    ("sk_sturm_graz", "SK Puntigamer Sturm Graz", "Sturm Graz"),
    ("fc_red_bull_salzburg", "FC Red Bull Salzburg", "Salzburg"),
    ("fk_austria_wien", "FK Austria Wien", "Austria Wien"),
    ("sk_rapid", "SK Rapid", "SK Rapid"),
    ("tsv_hartberg", "TSV Egger Glas Hartberg", "TSV Hartberg"),
    ("sv_ried", "SV Oberbank Ried", "SV Ried"),
    ("wolfsberger_ac", "RZ Pellets WAC", "Wolfsberger AC"),
    ("scr_altach", "SCR Altach", "SCR Altach"),
    ("grazer_ak_1902", "Grazer AK 1902", "Grazer AK"),
    ("wsg_tirol", "WSG Tirol", "WSG Tirol"),
    ("sc_austria_lustenau", "SC Austria Lustenau", "Austria Lustenau"),
)

NATIONS_LEAGUE_A_2026_27_TEAMS = (
    ("france", "France", "France", "FR"),
    ("italy", "Italy", "Italy", "IT"),
    ("belgium", "Belgium", "Belgium", "BE"),
    ("turkiye", "Türkiye", "Türkiye", "TR"),
    ("germany", "Germany", "Germany", "DE"),
    ("netherlands", "Netherlands", "Netherlands", "NL"),
    ("serbia", "Serbia", "Serbia", "RS"),
    ("greece", "Greece", "Greece", "GR"),
    ("spain", "Spain", "Spain", "ES"),
    ("croatia", "Croatia", "Croatia", "HR"),
    ("england_national_team", "England", "England", "GB-ENG"),
    ("czechia", "Czechia", "Czechia", "CZ"),
    ("portugal", "Portugal", "Portugal", "PT"),
    ("denmark", "Denmark", "Denmark", "DK"),
    ("norway", "Norway", "Norway", "NO"),
    ("wales_national_team", "Wales", "Wales", "GB-WLS"),
)

NATIONS_LEAGUE_B_C_D_2026_27_TEAMS = (
    ("slovenia", "Slovenia", "Slovenia", "SI"),
    ("scotland", "Scotland", "Scotland", "GB-SCT"),
    ("north_macedonia", "North Macedonia", "North Macedonia", "MK"),
    ("switzerland", "Switzerland", "Switzerland", "CH"),
    ("georgia", "Georgia", "Georgia", "GE"),
    ("northern_ireland", "Northern Ireland", "Northern Ireland", "GB-NIR"),
    ("hungary", "Hungary", "Hungary", "HU"),
    ("ukraine", "Ukraine", "Ukraine", "UA"),
    ("austria", "Austria", "Austria", "AT"),
    ("israel", "Israel", "Israel", "IL"),
    ("kosovo", "Kosovo", "Kosovo", "XK"),
    ("republic_of_ireland", "Republic of Ireland", "Republic of Ireland", "IE"),
    ("poland", "Poland", "Poland", "PL"),
    (
        "bosnia_and_herzegovina",
        "Bosnia and Herzegovina",
        "Bosnia and Herzegovina",
        "BA",
    ),
    ("sweden", "Sweden", "Sweden", "SE"),
    ("romania", "Romania", "Romania", "RO"),
    ("albania", "Albania", "Albania", "AL"),
    ("finland", "Finland", "Finland", "FI"),
    ("belarus", "Belarus", "Belarus", "BY"),
    ("san_marino", "San Marino", "San Marino", "SM"),
    ("montenegro", "Montenegro", "Montenegro", "ME"),
    ("armenia", "Armenia", "Armenia", "AM"),
    ("cyprus", "Cyprus", "Cyprus", "CY"),
    ("latvia", "Latvia", "Latvia", "LV"),
    ("kazakhstan", "Kazakhstan", "Kazakhstan", "KZ"),
    ("slovakia", "Slovakia", "Slovakia", "SK"),
    ("faroe_islands", "Faroe Islands", "Faroe Islands", "FO"),
    ("moldova", "Moldova", "Moldova", "MD"),
    ("bulgaria", "Bulgaria", "Bulgaria", "BG"),
    ("luxembourg", "Luxembourg", "Luxembourg", "LU"),
    ("iceland", "Iceland", "Iceland", "IS"),
    ("estonia", "Estonia", "Estonia", "EE"),
    ("andorra", "Andorra", "Andorra", "AD"),
    ("malta", "Malta", "Malta", "MT"),
    ("gibraltar", "Gibraltar", "Gibraltar", "GI"),
    ("lithuania", "Lithuania", "Lithuania", "LT"),
    ("azerbaijan", "Azerbaijan", "Azerbaijan", "AZ"),
    ("liechtenstein", "Liechtenstein", "Liechtenstein", "LI"),
)

CONFERENCE_LEAGUE_2026_27_TEAMS = (
    ("fc_lugano", "FC Lugano", "Lugano", "CH"),
    ("crvena_zvezda", "FK Crvena Zvezda", "Crvena Zvezda", "RS"),
    ("hajduk_split", "HNK Hajduk Split", "Hajduk Split", "HR"),
    ("ajax", "AFC Ajax", "Ajax", "NL"),
    ("gent", "KAA Gent", "Gent", "BE"),
    ("aarhus", "AGF Aarhus", "Aarhus", "DK"),
    ("egnatia", "KF Egnatia", "Egnatia", "AL"),
    ("midtjylland", "FC Midtjylland", "Midtjylland", "DK"),
    ("kups_kuopio", "KuPS Kuopio", "KuPS Kuopio", "FI"),
    ("trabzonspor", "Trabzonspor", "Trabzonspor", "TR"),
    ("mjallby", "Mjällby AIF", "Mjällby", "SE"),
    (
        "inter_escaldes",
        "Inter Club d'Escaldes",
        "Inter Escaldes",
        "AD",
    ),
    ("panathinaikos", "Panathinaikos FC", "Panathinaikos", "GR"),
    ("borac_banja_luka", "FK Borac Banja Luka", "Borac", "BA"),
    ("cska_sofia", "PFC CSKA Sofia", "CSKA Sofia", "BG"),
    ("monaco", "AS Monaco", "Monaco", "MC"),
    ("riga", "Riga FC", "Riga", "LV"),
    ("kairat_almaty", "FC Kairat Almaty", "Kairat Almaty", "KZ"),
    (
        "universitatea_craiova",
        "Universitatea Craiova",
        "Universitatea Craiova",
        "RO",
    ),
    ("getafe", "Getafe CF", "Getafe", "ES"),
    ("atalanta", "Atalanta BC", "Atalanta", "IT"),
    ("pafos", "Pafos FC", "Pafos", "CY"),
    (
        "brighton_and_hove_albion",
        "Brighton & Hove Albion",
        "Brighton",
        "GB-ENG",
    ),
    ("kauno_zalgiris", "FK Kauno Žalgiris", "Kauno Žalgiris", "LT"),
    ("copenhagen", "FC Copenhagen", "Copenhagen", "DK"),
    ("braga", "SC Braga", "Braga", "PT"),
    ("twente", "FC Twente", "Twente", "NL"),
    ("thun", "FC Thun", "Thun", "CH"),
    (
        "heart_of_midlothian",
        "Heart of Midlothian FC",
        "Hearts",
        "GB-SCT",
    ),
    ("nordsjaelland", "FC Nordsjælland", "Nordsjælland", "DK"),
    (
        "sint_truidense",
        "Sint-Truidense VV",
        "Sint-Truidense",
        "BE",
    ),
    ("iberia_tbilisi", "FC Iberia 1999", "Iberia Tbilisi", "GE"),
    ("sc_freiburg", "SC Freiburg", "Freiburg", "DE"),
    ("jablonec", "FK Jablonec", "Jablonec", "CZ"),
    ("brann", "SK Brann", "Brann", "NO"),
    (
        "lincoln_red_imps",
        "Lincoln Red Imps FC",
        "Lincoln Red Imps",
        "GI",
    ),
)

CHAMPIONS_LEAGUE_2026_27_TEAMS = (
    ("borussia_dortmund", "Borussia Dortmund", "Dortmund", "DE"),
    ("vfb_stuttgart", "VfB Stuttgart", "Stuttgart", "DE"),
    ("fc_bayern_muenchen", "FC Bayern München", "Bayern", "DE"),
    ("barcelona", "FC Barcelona", "Barcelona", "ES"),
    ("fenerbahce", "Fenerbahçe", "Fenerbahçe", "TR"),
    ("liverpool", "Liverpool", "Liverpool", "GB-ENG"),
    ("porto", "FC Porto", "Porto", "PT"),
    ("psv_eindhoven", "PSV Eindhoven", "PSV", "NL"),
    ("roma", "AS Roma", "Roma", "IT"),
    ("villarreal", "Villarreal CF", "Villarreal", "ES"),
    ("aston_villa", "Aston Villa", "Aston Villa", "GB-ENG"),
    ("inter_milan", "Inter", "Inter", "IT"),
    ("real_madrid", "Real Madrid", "Real Madrid", "ES"),
    ("shakhtar_donetsk", "Shakhtar Donetsk", "Shakhtar", "UA"),
    ("lille", "LOSC Lille", "Lille", "FR"),
    ("sporting_cp", "Sporting CP", "Sporting", "PT"),
    ("club_brugge", "Club Brugge", "Club Brugge", "BE"),
    ("aek_athens", "AEK Athens", "AEK", "GR"),
    ("viking", "Viking FK", "Viking", "NO"),
    ("rb_leipzig", "RB Leipzig", "RB Leipzig", "DE"),
    ("feyenoord", "Feyenoord", "Feyenoord", "NL"),
    ("real_betis", "Real Betis", "Real Betis", "ES"),
    ("paris_saint_germain", "Paris Saint-Germain", "Paris", "FR"),
    ("napoli", "SSC Napoli", "Napoli", "IT"),
    ("galatasaray", "Galatasaray", "Galatasaray", "TR"),
    ("manchester_united", "Manchester United", "Man Utd", "GB-ENG"),
    ("arsenal", "Arsenal", "Arsenal", "GB-ENG"),
    ("atletico_madrid", "Atlético de Madrid", "Atleti", "ES"),
    ("manchester_city", "Manchester City", "Man City", "GB-ENG"),
    ("slavia_prague", "Slavia Praha", "Slavia Praha", "CZ"),
    ("lask", "LASK", "LASK", "AT"),
    ("slovan_bratislava", "Slovan Bratislava", "Slovan", "SK"),
    ("bodo_glimt", "Bodø/Glimt", "Bodø/Glimt", "NO"),
    ("lens", "RC Lens", "Lens", "FR"),
    ("como", "Como 1907", "Como", "IT"),
    ("sabah", "Sabah FC", "Sabah", "AZ"),
)

NFL_2026_TEAMS = (
    ("arizona_cardinals", "Arizona Cardinals", "Cardinals", "ARI"),
    ("atlanta_falcons", "Atlanta Falcons", "Falcons", "ATL"),
    ("baltimore_ravens", "Baltimore Ravens", "Ravens", "BAL"),
    ("buffalo_bills", "Buffalo Bills", "Bills", "BUF"),
    ("carolina_panthers", "Carolina Panthers", "Panthers", "CAR"),
    ("chicago_bears", "Chicago Bears", "Bears", "CHI"),
    ("cincinnati_bengals", "Cincinnati Bengals", "Bengals", "CIN"),
    ("cleveland_browns", "Cleveland Browns", "Browns", "CLE"),
    ("dallas_cowboys", "Dallas Cowboys", "Cowboys", "DAL"),
    ("denver_broncos", "Denver Broncos", "Broncos", "DEN"),
    ("detroit_lions", "Detroit Lions", "Lions", "DET"),
    ("green_bay_packers", "Green Bay Packers", "Packers", "GB"),
    ("houston_texans", "Houston Texans", "Texans", "HOU"),
    ("indianapolis_colts", "Indianapolis Colts", "Colts", "IND"),
    ("jacksonville_jaguars", "Jacksonville Jaguars", "Jaguars", "JAX"),
    ("kansas_city_chiefs", "Kansas City Chiefs", "Chiefs", "KC"),
    ("los_angeles_rams", "Los Angeles Rams", "Rams", "LA"),
    ("los_angeles_chargers", "Los Angeles Chargers", "Chargers", "LAC"),
    ("las_vegas_raiders", "Las Vegas Raiders", "Raiders", "LV"),
    ("miami_dolphins", "Miami Dolphins", "Dolphins", "MIA"),
    ("minnesota_vikings", "Minnesota Vikings", "Vikings", "MIN"),
    ("new_england_patriots", "New England Patriots", "Patriots", "NE"),
    ("new_orleans_saints", "New Orleans Saints", "Saints", "NO"),
    ("new_york_giants", "New York Giants", "Giants", "NYG"),
    ("new_york_jets", "New York Jets", "Jets", "NYJ"),
    ("philadelphia_eagles", "Philadelphia Eagles", "Eagles", "PHI"),
    ("pittsburgh_steelers", "Pittsburgh Steelers", "Steelers", "PIT"),
    ("seattle_seahawks", "Seattle Seahawks", "Seahawks", "SEA"),
    ("san_francisco_49ers", "San Francisco 49ers", "49ers", "SF"),
    ("tampa_bay_buccaneers", "Tampa Bay Buccaneers", "Buccaneers", "TB"),
    ("tennessee_titans", "Tennessee Titans", "Titans", "TEN"),
    ("washington_commanders", "Washington Commanders", "Commanders", "WAS"),
)

SEASON_PARTICIPANTS_CATALOG = (
    SeasonParticipantsCatalogEntry(
        sport_key="football",
        competition_key="premier_league",
        season_key="2026_27",
        country_code="GB-ENG",
        participants=tuple(
            ParticipantCatalogEntry(
                participant_key=participant_key,
                name=name,
                short_name=short_name,
            )
            for participant_key, name, short_name in PREMIER_LEAGUE_2026_27_TEAMS
        ),
    ),
    SeasonParticipantsCatalogEntry(
        sport_key="football",
        competition_key="bundesliga",
        season_key="2026_27",
        country_code="DE",
        participants=tuple(
            ParticipantCatalogEntry(
                participant_key=participant_key,
                name=name,
                short_name=short_name,
            )
            for participant_key, name, short_name in BUNDESLIGA_2026_27_TEAMS
        ),
    ),
    SeasonParticipantsCatalogEntry(
        sport_key="football",
        competition_key="austrian_bundesliga",
        season_key="2026_27",
        country_code="AT",
        participants=tuple(
            ParticipantCatalogEntry(
                participant_key=participant_key,
                name=name,
                short_name=short_name,
            )
            for participant_key, name, short_name in (AUSTRIAN_BUNDESLIGA_2026_27_TEAMS)
        ),
    ),
    SeasonParticipantsCatalogEntry(
        sport_key="football",
        competition_key="championship",
        season_key="2026_27",
        country_code="GB-ENG",
        participants=tuple(
            ParticipantCatalogEntry(
                participant_key=participant_key,
                name=name,
                short_name=short_name,
                country_code=country_code,
            )
            for participant_key, name, short_name, country_code in (
                CHAMPIONSHIP_2026_27_TEAMS
            )
        ),
    ),
    SeasonParticipantsCatalogEntry(
        sport_key="football",
        competition_key="efl_cup",
        season_key="2026_27",
        country_code="GB-ENG",
        participants=tuple(
            ParticipantCatalogEntry(
                participant_key=participant_key,
                name=name,
                short_name=short_name,
                country_code=country_code,
            )
            for participant_key, name, short_name, country_code in (
                EFL_CUP_2026_27_TEAMS
            )
        ),
    ),
    SeasonParticipantsCatalogEntry(
        sport_key="football",
        competition_key="second_bundesliga",
        season_key="2026_27",
        country_code="DE",
        participants=tuple(
            ParticipantCatalogEntry(
                participant_key=participant_key,
                name=name,
                short_name=short_name,
            )
            for participant_key, name, short_name in SECOND_BUNDESLIGA_2026_27_TEAMS
        ),
    ),
    SeasonParticipantsCatalogEntry(
        sport_key="football",
        competition_key="dfb_pokal",
        season_key="2026_27",
        country_code="DE",
        participants=tuple(
            ParticipantCatalogEntry(
                participant_key=participant_key,
                name=name,
                short_name=short_name,
            )
            for participant_key, name, short_name in DFB_POKAL_2026_27_TEAMS
        ),
    ),
    SeasonParticipantsCatalogEntry(
        sport_key="football",
        competition_key="oefb_cup",
        season_key="2026_27",
        country_code="AT",
        participants=tuple(
            ParticipantCatalogEntry(
                participant_key=participant_key,
                name=name,
                short_name=short_name,
            )
            for participant_key, name, short_name in OEFB_CUP_2026_27_TEAMS
        ),
    ),
    SeasonParticipantsCatalogEntry(
        sport_key="football",
        competition_key="uefa_nations_league",
        season_key="2026_27",
        country_code="INT",
        participants=tuple(
            ParticipantCatalogEntry(
                participant_key=participant_key,
                name=name,
                short_name=short_name,
                country_code=country_code,
            )
            for participant_key, name, short_name, country_code in (
                NATIONS_LEAGUE_A_2026_27_TEAMS + NATIONS_LEAGUE_B_C_D_2026_27_TEAMS
            )
        ),
    ),
    SeasonParticipantsCatalogEntry(
        sport_key="football",
        competition_key="uefa_conference_league",
        season_key="2026_27",
        country_code="INT",
        participants=tuple(
            ParticipantCatalogEntry(
                participant_key=participant_key,
                name=name,
                short_name=short_name,
                country_code=country_code,
            )
            for participant_key, name, short_name, country_code in (
                CONFERENCE_LEAGUE_2026_27_TEAMS
            )
        ),
    ),
    SeasonParticipantsCatalogEntry(
        sport_key="football",
        competition_key="uefa_champions_league",
        season_key="2026_27",
        country_code="INT",
        participants=tuple(
            ParticipantCatalogEntry(
                participant_key=participant_key,
                name=name,
                short_name=short_name,
                country_code=country_code,
            )
            for participant_key, name, short_name, country_code in (
                CHAMPIONS_LEAGUE_2026_27_TEAMS
            )
        ),
    ),
    SeasonParticipantsCatalogEntry(
        sport_key="american_football",
        competition_key="nfl",
        season_key="2026",
        country_code="US",
        participants=tuple(
            ParticipantCatalogEntry(
                participant_key=participant_key,
                name=name,
                short_name=short_name,
            )
            for participant_key, name, short_name, _ in NFL_2026_TEAMS
        ),
    ),
)


def initialize_participants_catalog(
    repository: ParticipantsRepository,
    season_participants_repository: SeasonParticipantsRepository,
    sports_repository: SportsRepository,
    competitions_repository: CompetitionsRepository,
    seasons_repository: SeasonsRepository,
) -> ParticipantsCatalogResult:
    participants: list[Participant] = []
    memberships: list[SeasonParticipant] = []
    for catalog_entry in SEASON_PARTICIPANTS_CATALOG:
        sport = sports_repository.get_by_key(catalog_entry.sport_key)
        if sport is None:
            raise RuntimeError(
                "Required sport not found for participants catalog: "
                f"{catalog_entry.sport_key}"
            )
        competition = competitions_repository.get_by_key(
            sport_id=sport.id,
            competition_key=catalog_entry.competition_key,
        )
        if competition is None:
            raise RuntimeError(
                "Required competition not found for participants catalog: "
                f"{catalog_entry.competition_key}"
            )
        season = seasons_repository.get_by_key(
            competition_id=competition.id,
            season_key=catalog_entry.season_key,
        )
        if season is None:
            raise RuntimeError(
                "Required season not found for participants catalog: "
                f"{catalog_entry.competition_key}/{catalog_entry.season_key}"
            )
        catalog_participants = [
            repository.upsert(
                sport_id=sport.id,
                participant_key=entry.participant_key,
                participant_type="team",
                name=entry.name,
                short_name=entry.short_name,
                country_code=entry.country_code or catalog_entry.country_code,
            )
            for entry in catalog_entry.participants
        ]
        participants.extend(catalog_participants)
        memberships.extend(
            season_participants_repository.upsert(
                season_id=season.id,
                participant_id=participant.id,
            )
            for participant in catalog_participants
        )

    return ParticipantsCatalogResult(
        participants=participants,
        season_participants=memberships,
    )
