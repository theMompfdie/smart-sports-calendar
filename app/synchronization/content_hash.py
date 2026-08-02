import hashlib
import hmac
import json
import re

from app.synchronization.outlook_event_payload_builder import OutlookEventPayload

_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


def calculate_content_hash(payload: OutlookEventPayload) -> str:
    canonical_payload = json.dumps(
        payload.to_graph_dict(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()


def has_content_changed(
    payload: OutlookEventPayload,
    persisted_content_hash: str | None,
) -> bool:
    if persisted_content_hash is None:
        return True

    if _SHA256_PATTERN.fullmatch(persisted_content_hash) is None:
        raise ValueError(
            "Persisted content hash must be a 64-character SHA-256 hexadecimal digest."
        )

    calculated_content_hash = calculate_content_hash(payload)

    return not hmac.compare_digest(
        calculated_content_hash,
        persisted_content_hash.lower(),
    )
