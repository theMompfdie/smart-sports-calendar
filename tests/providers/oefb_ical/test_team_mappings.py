from app.database.participants_catalog import OEFB_CUP_2026_27_TEAMS
from app.providers.oefb_ical.team_mappings import (
    OEFB_CUP_TEAM_MAPPINGS,
    resolve_team_key,
)


def test_reviewed_mapping_matches_canonical_64_team_catalog() -> None:
    catalog_by_key = {
        participant_key: name
        for participant_key, name, _short_name in OEFB_CUP_2026_27_TEAMS
    }

    assert len(OEFB_CUP_TEAM_MAPPINGS) == 64
    assert len(catalog_by_key) == 64
    assert {
        mapping.participant_key for mapping in OEFB_CUP_TEAM_MAPPINGS.values()
    } == set(catalog_by_key)
    assert all(
        mapping.provider_name == catalog_by_key[mapping.participant_key]
        for mapping in OEFB_CUP_TEAM_MAPPINGS.values()
    )


def test_reviewed_mapping_preserves_observed_boundary_identities() -> None:
    assert resolve_team_key(1027) == "wiener_viktoria"
    assert resolve_team_key(9110) == "wolfsberger_ac"
    assert resolve_team_key(999999) is None
