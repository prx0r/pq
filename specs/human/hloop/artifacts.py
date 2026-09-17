from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import hashlib, json, secrets

@dataclass(frozen=True)
class ArtifactRef:
    id: str
    kind: str
    content_hash: str
    secret: bool
    metadata: dict[str,Any]

class ArtifactVault:
    """Reference vault.

    Secret payloads are never returned to the model-facing event stream. The
    in-memory reference implementation is intentionally not a production secret
    manager; production should bind to the credential broker / OS keychain / HSM.
    """
    def __init__(self):
        self._payloads={}
        self._refs={}

    def put(self,kind:str,payload:str|bytes,*,secret:bool=False,metadata=None)->ArtifactRef:
        b=payload.encode() if isinstance(payload,str) else payload
        h="sha256:"+hashlib.sha256(b).hexdigest()
        rid="artifact:"+secrets.token_hex(16)
        ref=ArtifactRef(rid,kind,h,secret,metadata or {})
        self._payloads[rid]=b
        self._refs[rid]=ref
        return ref

    def ref(self,rid):
        return self._refs[rid]

    def model_projection(self,rid):
        ref=self.ref(rid)
        return {
            "id":ref.id,"kind":ref.kind,"content_hash":ref.content_hash,
            "secret":ref.secret,"metadata":ref.metadata
        }
