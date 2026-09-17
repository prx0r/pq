from __future__ import annotations
import hashlib,json
from typing import Any

def canonical_bytes(obj:Any)->bytes:
    return json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode("utf-8")

def sha256_hex(obj:Any)->str:
    b=obj if isinstance(obj,(bytes,bytearray)) else canonical_bytes(obj)
    return hashlib.sha256(b).hexdigest()

def obj_id(prefix:str,obj:Any)->str:
    return f"{prefix}:{sha256_hex(obj)}"
