"""Canonical identity: full SHA-256, always. No truncated ids on any real
evidence path (devplan §11). Same canonical-byte algorithm as qp/ab1
(sorted keys, no whitespace, UTF-8) so hashes agree across modules.
"""
import hashlib
import json


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def obj_id(prefix: str, obj) -> str:
    """Full 64-hex content id. Display may truncate; identity never does."""
    return prefix + ":" + sha256_hex(canonical(obj))


def merkle_root(leaves):
    if not leaves:
        return sha256_hex(b"")
    level = list(leaves)
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            pair = level[i] + (level[i + 1] if i + 1 < len(level) else level[i])
            nxt.append(sha256_hex(pair.encode("utf-8")))
        level = nxt
    return level[0]
