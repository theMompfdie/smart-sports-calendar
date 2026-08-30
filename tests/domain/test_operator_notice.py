import pytest
from app.domain.operator_notice import MAX_OPERATOR_NOTICE_LENGTH, OperatorNotice


def test_operator_notice_accepts_bounded_normalized_plain_text() -> None:
    notice = OperatorNotice("Subject to schedule changes.")

    assert notice.text == "Subject to schedule changes."


@pytest.mark.parametrize(
    "value", ["", " notice", "notice ", "line\nbreak", "tab\ttext"]
)
def test_operator_notice_rejects_blank_untrimmed_or_control_text(value: str) -> None:
    with pytest.raises(ValueError):
        OperatorNotice(value)


def test_operator_notice_rejects_oversized_text() -> None:
    with pytest.raises(ValueError, match="maximum length"):
        OperatorNotice("x" * (MAX_OPERATOR_NOTICE_LENGTH + 1))
