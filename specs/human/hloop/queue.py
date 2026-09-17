from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any
from datetime import datetime, timezone
import hashlib, json

class HumanTaskKind(str,Enum):
    DECISION="DECISION"
    ACCOUNT_CREATION="ACCOUNT_CREATION"
    OWNER_2FA="OWNER_2FA"
    PHYSICAL_ACTION="PHYSICAL_ACTION"
    CREDENTIAL_BOOTSTRAP="CREDENTIAL_BOOTSTRAP"
    CODE_OR_TEXT="CODE_OR_TEXT"
    STRATEGIC_DIRECTION="STRATEGIC_DIRECTION"
    LEGAL_ATTESTATION="LEGAL_ATTESTATION"

@dataclass
class HumanTask:
    id: str
    parent_atask_id: str
    kind: HumanTaskKind
    title: str
    instruction: str
    expected_artifact_type: str | None
    consequence_class: str
    risk_band: str
    proof_family: str
    project: str
    options: dict[int,str]
    evidence_refs: list[str]=field(default_factory=list)
    alternatives_checked: list[dict[str,Any]]=field(default_factory=list)
    downstream_unblock_count: int=0
    expires_at: str | None=None
    created_at: str | None=None
    state: str="OPEN"
    prediction_ref: str | None=None
    resolution_ref: str | None=None

    def payload_hash(self) -> str:
        d=asdict(self)
        # Mutable runtime state isn't part of requested-action identity.
        for k in ("state","prediction_ref","resolution_ref"):
            d.pop(k,None)
        return "sha256:"+hashlib.sha256(
            json.dumps(d,sort_keys=True,default=str,separators=(",",":")).encode()
        ).hexdigest()

class HumanQueue:
    def __init__(self):
        self.tasks: dict[str,HumanTask]={}

    def add(self,task:HumanTask):
        if task.id in self.tasks:
            raise ValueError("duplicate human task")
        if task.created_at is None:
            task.created_at=datetime.now(timezone.utc).isoformat()
        self.tasks[task.id]=task

    def open(self):
        return sorted(
            [x for x in self.tasks.values() if x.state in {"OPEN","WAITING_ARTIFACT"}],
            key=lambda x:(-x.downstream_unblock_count,x.risk_band,x.created_at or "")
        )

    def get(self,task_id):
        return self.tasks[task_id]

    def resolve(self,task_id,resolution_ref):
        t=self.get(task_id)
        if t.state not in {"OPEN","WAITING_ARTIFACT"}:
            raise ValueError("human task not unresolved")
        t.state="RESOLVED"
        t.resolution_ref=resolution_ref
