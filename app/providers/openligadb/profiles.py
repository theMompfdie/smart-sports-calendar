from dataclasses import dataclass
from datetime import date

from app.domain.competition_lifecycle import CompetitionFormat, TournamentStageKind


@dataclass(frozen=True)
class OpenLigaDBCompetitionProfile:
    canonical_competition_key: str
    canonical_season_key: str
    competition_name: str
    league_id: int
    league_shortcut: str
    league_season: int
    sport_id: int
    season_start_date: date
    season_end_date: date
    round_capacities: tuple[int, ...]
    competition_format: CompetitionFormat
    normalized_stage: str
    round_prefix: str
    stage_kind: TournamentStageKind | None = None
    expected_fixture_count: int | None = None
    expected_participant_count: int | None = None
    require_complete_double_round_robin: bool = False
    require_complete_group_double_round_robin: bool = False
    allow_additional_groups: bool = False
    allow_missing_timezone_id: bool = False

    def __post_init__(self) -> None:
        if not self.round_capacities or any(
            capacity <= 0 for capacity in self.round_capacities
        ):
            raise ValueError("OpenLigaDB round capacities must be positive")
        if self.expected_fixture_count is not None and self.expected_fixture_count <= 0:
            raise ValueError("OpenLigaDB expected fixture count must be positive")
        if (
            self.expected_participant_count is not None
            and self.expected_participant_count <= 0
        ):
            raise ValueError("OpenLigaDB expected participant count must be positive")
        if (
            self.require_complete_double_round_robin
            and self.require_complete_group_double_round_robin
        ):
            raise ValueError("OpenLigaDB profiles cannot require two round-robin modes")
        if (
            self.require_complete_double_round_robin
            or self.require_complete_group_double_round_robin
        ) and (
            self.expected_fixture_count is None
            or self.expected_participant_count is None
        ):
            raise ValueError(
                "OpenLigaDB round-robin profiles require expected fixture and "
                "participant counts"
            )
        if self.competition_format is CompetitionFormat.HYBRID_TOURNAMENT:
            if self.stage_kind is None:
                raise ValueError("OpenLigaDB hybrid profiles require a stage kind")
        elif self.stage_kind is not None:
            raise ValueError("OpenLigaDB stage kind is only valid for hybrid profiles")


DFB_POKAL_PROFILE = OpenLigaDBCompetitionProfile(
    canonical_competition_key="dfb_pokal",
    canonical_season_key="2026_27",
    competition_name="DFB-Pokal",
    league_id=4945,
    league_shortcut="dfb",
    league_season=2026,
    sport_id=1,
    season_start_date=date(2026, 8, 21),
    season_end_date=date(2027, 5, 29),
    round_capacities=(32, 16, 8, 4, 2, 1),
    competition_format=CompetitionFormat.KNOCKOUT_CUP,
    normalized_stage="knockout",
    round_prefix="round",
    allow_missing_timezone_id=True,
)

SECOND_BUNDESLIGA_PROFILE = OpenLigaDBCompetitionProfile(
    canonical_competition_key="second_bundesliga",
    canonical_season_key="2026_27",
    competition_name="2. Bundesliga",
    league_id=4938,
    league_shortcut="bl2",
    league_season=2026,
    sport_id=1,
    season_start_date=date(2026, 8, 7),
    season_end_date=date(2027, 5, 23),
    round_capacities=(9,) * 34,
    competition_format=CompetitionFormat.LEAGUE,
    normalized_stage="regular_season",
    round_prefix="matchday",
    expected_fixture_count=306,
    expected_participant_count=18,
    require_complete_double_round_robin=True,
    allow_missing_timezone_id=True,
)

NATIONS_LEAGUE_A_PROFILE = OpenLigaDBCompetitionProfile(
    canonical_competition_key="uefa_nations_league",
    canonical_season_key="2026_27",
    competition_name="UEFA Nations League A",
    league_id=5978,
    league_shortcut="nla",
    league_season=2026,
    sport_id=1,
    season_start_date=date(2026, 9, 24),
    season_end_date=date(2026, 11, 17),
    round_capacities=(12, 12, 12, 12),
    competition_format=CompetitionFormat.HYBRID_TOURNAMENT,
    normalized_stage="league_a_group_phase",
    round_prefix="group-a",
    stage_kind=TournamentStageKind.LEAGUE_PHASE,
    expected_fixture_count=48,
    expected_participant_count=16,
    require_complete_group_double_round_robin=True,
    allow_additional_groups=True,
)

OPENLIGADB_COMPETITION_PROFILES = {
    (profile.canonical_competition_key, profile.canonical_season_key): profile
    for profile in (
        DFB_POKAL_PROFILE,
        SECOND_BUNDESLIGA_PROFILE,
        NATIONS_LEAGUE_A_PROFILE,
    )
}


def get_competition_profile(
    competition_key: str, season_key: str
) -> OpenLigaDBCompetitionProfile | None:
    return OPENLIGADB_COMPETITION_PROFILES.get((competition_key, season_key))
