"""A-COM kernel: canonical serialization, hashing, stable IDs.

Rule: identical semantic content ALWAYS produces identical bytes.
No timestamps, no dict-order luck, no float formatting drift.
If two receipts hash differently, they ARE different. (northstar §4)
"""

import hashlib
import json

PROTOCOL = "acom/0.1"


def canonical(obj) -> bytes:
    """Canonical JSON bytes: sorted keys, no whitespace, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    """Hex digest. The only hash in the kernel besides Merkle joins."""
    return hashlib.sha256(data).hexdigest()


def obj_id(prefix: str, obj) -> str:
    """Stable content-derived ID: <prefix>:<12 hex chars>."""
    return f"{prefix}:{sha256_hex(canonical(obj))[:12]}"


def merkle_root(leaves: list[str]) -> str:
    """Merkle root over hex leaf hashes. Empty tree = hash of empty."""
    level = list(leaves)
    if not level:
        return sha256_hex(b"")
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            pair = level[i] + (level[i + 1] if i + 1 < len(level) else level[i])
            nxt.append(sha256_hex(pair.encode()))
        level = nxt
    return level[0]
