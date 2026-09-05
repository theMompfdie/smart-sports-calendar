"""Private file transport. CLI clients never open SQLite or Microsoft Graph."""

import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

from app.imports.manual_files import read_bounded
from app.imports.manual_manifest import IDENTIFIER

MAX_TRANSPORT_BYTES = 16 * 1024 * 1024


def encoded(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=True, separators=(",", ":")
    ).encode()


def identifier(value: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError("Invalid transport identifier.")
    return value


def atomic_write(path: Path, payload: bytes, *, immutable: bool = False) -> None:
    if path.is_symlink():
        raise ValueError("Transport files must not be symlinks.")
    temporary = path.with_name("." + uuid4().hex + ".upload")
    try:
        with temporary.open("xb") as handle:
            os.chmod(temporary, 0o600)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if immutable:
            try:
                os.link(temporary, path)
            except FileExistsError:
                if read_bounded(path, limit=MAX_TRANSPORT_BYTES) != payload:
                    raise ValueError("Immutable transport collision.") from None
        else:
            os.replace(temporary, path)
        if os.name != "nt":
            descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)


class ManualInbox:
    def __init__(self, root: Path, instance: str):
        if not root.is_absolute():
            raise ValueError("Inbox path must be absolute.")
        self.root = root
        self.instance = identifier(instance)

    def initialize(self) -> None:
        if any(part.is_symlink() for part in (self.root, *self.root.parents)):
            raise ValueError("Inbox directories must not be symlinks.")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        for name in ("pending", "archive", "results", "profiles"):
            path = self.root / name
            if path.is_symlink():
                raise ValueError("Inbox directories must not be symlinks.")
            path.mkdir(exist_ok=True, mode=0o700)
        atomic_write(
            self.root / "instance.json",
            encoded({"instance": self.instance}),
            immutable=True,
        )

    def verify(self) -> None:
        if any(part.is_symlink() for part in (self.root, *self.root.parents)):
            raise ValueError("Inbox directories must not be symlinks.")
        if json.loads(read_bounded(self.root / "instance.json")) != {
            "instance": self.instance
        }:
            raise ValueError("Inbox belongs to another instance.")
        for name in ("pending", "archive", "results", "profiles"):
            if (self.root / name).is_symlink() or not (self.root / name).is_dir():
                raise ValueError("Inbox directory is unavailable.")

    def submit(
        self, action: str, namespace: str, submission: str, payload: bytes = b""
    ) -> str:
        self.verify()
        if action not in {"submit", "approve", "preview"}:
            raise ValueError("Unknown inbox action.")
        request = encoded(
            {
                "request_id": uuid4().hex if action == "preview" else None,
                "action": action,
                "namespace": identifier(namespace),
                "submission_id": identifier(submission),
                "instance": self.instance,
                "payload": payload.decode("utf-8"),
            }
        )
        if len(request) > MAX_TRANSPORT_BYTES:
            raise ValueError("Encoded inbox request exceeds the size limit.")
        digest = hashlib.sha256(request).hexdigest()
        # Archived delivery is already durable; do not requeue it implicitly.
        archive = self.root / "archive" / (digest + ".json")
        if archive.exists():
            if read_bounded(archive, limit=MAX_TRANSPORT_BYTES) != request:
                raise ValueError("Immutable transport collision.")
        else:
            atomic_write(
                self.root / "pending" / (digest + ".json"), request, immutable=True
            )
        return digest

    def status(self, namespace: str, submission: str) -> dict:
        self.verify()
        path = self.result_path(namespace, submission)
        if not path.exists():
            raise FileNotFoundError("Worker has not published this status yet.")
        return json.loads(read_bounded(path, limit=MAX_TRANSPORT_BYTES))

    def result_path(self, namespace: str, submission: str) -> Path:
        key = identifier(namespace) + ":" + identifier(submission)
        return (
            self.root / "results" / (hashlib.sha256(key.encode()).hexdigest() + ".json")
        )
