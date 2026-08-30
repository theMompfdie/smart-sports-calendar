"""Validated operator-facing notice text for synchronized sports events."""

import unicodedata
from dataclasses import dataclass

MAX_OPERATOR_NOTICE_LENGTH = 280
OPERATOR_NOTICE_METADATA_KEY = "operator_notice"


@dataclass(frozen=True)
class OperatorNotice:
    """Bounded plain text that may be rendered in an Outlook event body."""

    text: str

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise TypeError("Operator notice must be text.")
        if not self.text or self.text != self.text.strip():
            raise ValueError("Operator notice must be normalized non-blank text.")
        if len(self.text) > MAX_OPERATOR_NOTICE_LENGTH:
            raise ValueError(
                "Operator notice exceeds the maximum length of "
                f"{MAX_OPERATOR_NOTICE_LENGTH} characters."
            )
        if any(
            unicodedata.category(character).startswith("C") for character in self.text
        ):
            raise ValueError("Operator notice must not contain control characters.")
