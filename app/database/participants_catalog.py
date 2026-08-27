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


@dataclass(frozen=True)
class SeasonParticipantsCatalogEntry:
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

SEASON_PARTICIPANTS_CATALOG = (
    SeasonParticipantsCatalogEntry(
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
)


def initialize_participants_catalog(
    repository: ParticipantsRepository,
    season_participants_repository: SeasonParticipantsRepository,
    sports_repository: SportsRepository,
    competitions_repository: CompetitionsRepository,
    seasons_repository: SeasonsRepository,
) -> ParticipantsCatalogResult:
    football = sports_repository.get_by_key("football")
    if football is None:
        raise RuntimeError(
            "Required sport not found for participants catalog: football"
        )

    participants: list[Participant] = []
    memberships: list[SeasonParticipant] = []
    for catalog_entry in SEASON_PARTICIPANTS_CATALOG:
        competition = competitions_repository.get_by_key(
            sport_id=football.id,
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
                sport_id=football.id,
                participant_key=entry.participant_key,
                participant_type="team",
                name=entry.name,
                short_name=entry.short_name,
                country_code=catalog_entry.country_code,
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
