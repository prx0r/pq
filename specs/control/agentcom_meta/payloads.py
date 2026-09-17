from __future__ import annotations
from dataclasses import dataclass,asdict
from hashlib import sha256
from pathlib import Path
import json,os,time,secrets
from typing import Any

@dataclass(frozen=True)
class PayloadRef:
    id:str
    task_id:str
    kind:str
    sha256:str
    bytes:int
    created_at:float
    path:str

class HumanPayloadStore:
    """Local 0600 channel for human-provided text/code/secrets.

    Raw payload bytes do not enter agent logs, the policy-learning store, or dashboard snapshots.
    Callers receive a content hash + opaque reference. Production deployments should swap this
    filesystem store for the user's local vault/secret broker when appropriate.
    """
    def __init__(self,root:str|Path):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        try:os.chmod(self.root,0o700)
        except OSError:pass
    def put(self,task_id:str,kind:str,text:str)->PayloadRef:
        if kind not in {"text","code","secret"}:raise ValueError("unsupported-human-payload-kind")
        raw=str(text).encode("utf-8")
        digest=sha256(raw).hexdigest();rid="hp:"+sha256((task_id+"|"+kind+"|"+digest+"|"+secrets.token_hex(8)).encode()).hexdigest()
        p=self.root/(rid.replace(":","_")+".json")
        doc={"id":rid,"task_id":task_id,"kind":kind,"sha256":digest,"created_at":time.time(),"text":str(text)}
        fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,"w",encoding="utf-8") as f:json.dump(doc,f,ensure_ascii=False)
        return PayloadRef(rid,task_id,kind,digest,len(raw),doc["created_at"],str(p))
    def get(self,ref:PayloadRef|str)->str:
        rid=ref.id if isinstance(ref,PayloadRef) else str(ref)
        p=self.root/(rid.replace(":","_")+".json")
        doc=json.loads(p.read_text())
        raw=str(doc["text"]);assert sha256(raw.encode()).hexdigest()==doc["sha256"]
        return raw
    @staticmethod
    def public(ref:PayloadRef)->dict[str,Any]:
        d=asdict(ref);d.pop("path",None);return d
