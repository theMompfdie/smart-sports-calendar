import pytest
from app.providers.oefb_ical.exceptions import OefbIcalIntegrityError
from app.providers.oefb_ical.profiles import resolve_round


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("UNIQA ÖFB Cup - 1. Runde", ("round-1", 1)),
        ("6.Runde", ("round-6", 6)),
        ("Termin der 3. RUNDE", ("round-3", 3)),
    ],
)
def test_resolve_round_accepts_one_supported_round(
    description: str,
    expected: tuple[str, int],
) -> None:
    assert resolve_round(description) == expected


@pytest.mark.parametrize(
    "description",
    [
        "UNIQA ÖFB Cup",
        "1. Runde / 2. Runde",
        "7. Runde",
    ],
)
def test_resolve_round_rejects_missing_contradictory_or_unsupported_round(
    description: str,
) -> None:
    with pytest.raises(
        OefbIcalIntegrityError,
        match="missing or contradictory round",
    ):
        resolve_round(description)
