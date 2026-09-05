"""Bounded regular-file reads shared by manual import tools and transport."""

from pathlib import Path

from app.imports.manual_manifest import MAX_BYTES


def read_bounded(path: Path, *, limit: int = MAX_BYTES) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Input must be a regular local file.")
    with path.open("rb") as handle:
        payload = handle.read(limit + 1)
    if len(payload) > limit:
        raise ValueError("Input exceeds the size limit.")
    return payload
