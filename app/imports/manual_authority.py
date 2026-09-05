"""Explicit non-overlapping authority proposal for the Phase 9 apply extension."""

from dataclasses import dataclass

from app.imports.manual_manifest import IDENTIFIER


@dataclass(frozen=True)
class StageAuthority:
    writer: str
    stages: frozenset[str] | None  # None owns the whole competition/season.


def validate_stage_authorities(authorities: tuple[StageAuthority, ...]) -> None:
    """Validate one competition/season; never reinterpret legacy broad grants."""
    for index, authority in enumerate(authorities):
        if not authority.writer or authority.stages == frozenset():
            raise ValueError("Authority requires a writer and a nonempty boundary.")
        if authority.stages is not None and any(
            not IDENTIFIER.fullmatch(stage) for stage in authority.stages
        ):
            raise ValueError("Authority stages require explicit stable identifiers.")
        for previous in authorities[:index]:
            if (
                authority.writer == previous.writer
                or authority.stages is None
                or previous.stages is None
                or authority.stages.intersection(previous.stages)
            ):
                raise ValueError("Authority boundaries overlap or duplicate a writer.")
