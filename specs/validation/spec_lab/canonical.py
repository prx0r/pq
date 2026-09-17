from __future__ import annotations
import hashlib
import json
from typing import Any

def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def digest(tag: str, value: Any) -> str:
    raw = f"{tag}\0{canonical_json(value)}".encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()

def full_id(prefix: str, value: Any) -> str:
    return f"{prefix}:{digest(prefix, value).split(':', 1)[1]}"

def deep_copy(value: Any) -> Any:
    return json.loads(json.dumps(value))
