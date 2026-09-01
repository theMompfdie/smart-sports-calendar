from dataclasses import replace

import pytest
from app.synchronization.content_hash import (
    calculate_content_hash,
    has_content_changed,
)
from app.synchronization.outlook_event_payload_builder import (
    OutlookDateTime,
    OutlookEventPayload,
)


def create_payload() -> OutlookEventPayload:
    return OutlookEventPayload(
        subject="Austria Wien – Rapid Wien",
        body="<p>Status: scheduled</p><p>Sport: Football</p>",
        start=OutlookDateTime(
            date_time="2026-08-21T19:00:00",
            time_zone="Europe/Vienna",
        ),
        end=OutlookDateTime(
            date_time="2026-08-21T21:00:00",
            time_zone="Europe/Vienna",
        ),
        location="Vienna",
        categories=("Football", "SMART Sports Calendar"),
        is_all_day=False,
        is_reminder_on=True,
        reminder_minutes_before_start=15,
        show_as="busy",
    )


def test_calculate_content_hash_returns_expected_sha256_digest() -> None:
    payload = create_payload()

    content_hash = calculate_content_hash(payload)

    assert content_hash == (
        "1e381b999db31af88c155641253fc62ddadbbea120b988832a7807792e05c9d6"
    )


def test_calculate_content_hash_is_deterministic() -> None:
    payload = create_payload()

    first_hash = calculate_content_hash(payload)
    second_hash = calculate_content_hash(payload)

    assert first_hash == second_hash


def test_calculate_content_hash_changes_when_payload_changes() -> None:
    payload = create_payload()
    changed_payload = replace(
        payload,
        subject="Austria Wien – Rapid Wien (updated)",
    )

    assert calculate_content_hash(payload) != calculate_content_hash(changed_payload)


def test_calculate_content_hash_changes_when_html_body_changes() -> None:
    payload = create_payload()
    changed_payload = replace(
        payload,
        body="<p>Status: postponed</p><p>Sport: Football</p>",
    )

    assert calculate_content_hash(payload) != calculate_content_hash(changed_payload)


def test_has_content_changed_returns_false_for_matching_hash() -> None:
    payload = create_payload()
    persisted_content_hash = calculate_content_hash(payload)

    assert not has_content_changed(payload, persisted_content_hash)


def test_has_content_changed_accepts_uppercase_hash() -> None:
    payload = create_payload()
    persisted_content_hash = calculate_content_hash(payload).upper()

    assert not has_content_changed(payload, persisted_content_hash)


def test_has_content_changed_returns_true_for_changed_payload() -> None:
    payload = create_payload()
    persisted_content_hash = calculate_content_hash(payload)
    changed_payload = replace(
        payload,
        reminder_minutes_before_start=30,
    )

    assert has_content_changed(changed_payload, persisted_content_hash)


def test_has_content_changed_returns_true_without_persisted_hash() -> None:
    assert has_content_changed(create_payload(), None)


@pytest.mark.parametrize(
    "persisted_content_hash",
    [
        "",
        "abc",
        "g" * 64,
        "a" * 63,
        "a" * 65,
        f"{'a' * 64} ",
        f" {'a' * 64}",
    ],
)
def test_has_content_changed_rejects_invalid_persisted_hash(
    persisted_content_hash: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="Persisted content hash must be a 64-character SHA-256",
    ):
        has_content_changed(
            create_payload(),
            persisted_content_hash,
        )
