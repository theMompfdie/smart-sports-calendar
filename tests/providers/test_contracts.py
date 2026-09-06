from dataclasses import replace
from pathlib import Path

import pytest
from app.domain.competition_lifecycle import (
    FixtureLeg,
    FixtureParticipantResolution,
    TournamentStageKind,
)
from app.providers.contracts import (
    NormalizedFixtureContractError,
    NormalizedFixtureParticipant,
)

from tests.application.test_api_football_fixture_normalization_service import (
    create_context,
)
from tests.catalog_support import CatalogInitializer


def test_participant_resolution_is_explicit_and_fail_closed() -> None:
    resolved = NormalizedFixtureParticipant(42, "home", 1)
    unresolved = NormalizedFixtureParticipant(
        None,
        "away",
        2,
        FixtureParticipantResolution.UNRESOLVED,
    )

    assert resolved.resolved is True
    assert unresolved.resolved is False

    with pytest.raises(NormalizedFixtureContractError, match="positive ID"):
        NormalizedFixtureParticipant(None, "home", 1)
    with pytest.raises(NormalizedFixtureContractError, match="cannot reference"):
        NormalizedFixtureParticipant(
            42,
            "home",
            1,
            FixtureParticipantResolution.UNRESOLVED,
        )
    with pytest.raises(NormalizedFixtureContractError, match="position"):
        NormalizedFixtureParticipant(42, "home", 2)


def test_hybrid_fixture_lifecycle_metadata_is_typed(
    tmp_path: Path, initialize_test_catalog: CatalogInitializer
) -> None:
    fixture = create_context(
        tmp_path, initialize_test_catalog=initialize_test_catalog
    ).service.normalize_current_premier_league()[0]
    hybrid = replace(
        fixture,
        stage="qualifying",
        round_name="qualifying_round_3",
        stage_kind=TournamentStageKind.QUALIFYING,
        tie_key="qualifying_round_3_tie_17",
        leg=FixtureLeg.FIRST,
    )

    assert hybrid.stage_kind is TournamentStageKind.QUALIFYING
    assert hybrid.leg is FixtureLeg.FIRST
    assert hybrid.participants_resolved is True


def test_two_leg_fixture_requires_normalized_tie_key(
    tmp_path: Path, initialize_test_catalog: CatalogInitializer
) -> None:
    fixture = create_context(
        tmp_path, initialize_test_catalog=initialize_test_catalog
    ).service.normalize_current_premier_league()[0]

    with pytest.raises(NormalizedFixtureContractError, match="requires.*tie key"):
        replace(
            fixture,
            stage="knockout",
            stage_kind=TournamentStageKind.KNOCKOUT,
            leg=FixtureLeg.SECOND,
        )

    with pytest.raises(NormalizedFixtureContractError, match="normalized non-blank"):
        replace(
            fixture,
            stage="knockout",
            stage_kind=TournamentStageKind.KNOCKOUT,
            tie_key=" tie-17 ",
            leg=FixtureLeg.SECOND,
        )
