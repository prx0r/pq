from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any
from datetime import datetime, timezone
import hashlib,json,secrets

@dataclass
class Pocket:
    id: str
    asset: str
    balance_atomic: int
    max_single_spend_atomic: int
    label: str
    state: str="ACTIVE"

@dataclass
class GrantRequest:
    id: str
    subject: str
    capability: str
    pocket_id: str | None
    max_value_atomic: int | None
    asset: str | None
    max_calls: int
    expires_at: str
    reason: str
    proof_obligation_ids: list[str]
    status: str="PENDING"

class WalletLedger:
    """Reference bounded-pocket ledger.

    It deliberately stores no wallet seed. A real wallet adapter binds pocket IDs
    to an isolated signer/QP wallet service.
    """
    def __init__(self):
        self.pockets={}

    def add(self,pocket:Pocket):
        if pocket.id in self.pockets: raise ValueError("duplicate pocket")
        self.pockets[pocket.id]=pocket

    def reserve(self,pocket_id:str,amount_atomic:int):
        p=self.pockets[pocket_id]
        if p.state!="ACTIVE": return False,"pocket-inactive"
        if amount_atomic<0: return False,"negative"
        if amount_atomic>p.max_single_spend_atomic: return False,"single-spend-cap"
        if amount_atomic>p.balance_atomic: return False,"insufficient"
        p.balance_atomic -= amount_atomic
        return True,"reserved"

class GrantLedger:
    """UI/control-plane grant requests only.

    `approve()` emits a reference that a production QP authority service must
    convert into a signed grant. This object never fabricates cryptographic QP
    authority.
    """
    def __init__(self):
        self.requests={}

    def request(self, **kw):
        body=dict(kw)
        gid="grantreq:"+hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()
        req=GrantRequest(id=gid,**kw)
        self.requests[gid]=req
        return req

    def approve(self,grant_request_id:str):
        req=self.requests[grant_request_id]
        if req.status!="PENDING": raise ValueError("not pending")
        req.status="APPROVED_PENDING_QP"
        return {"grant_request_id":req.id,"qp_grant_ref":f"qpgrantref:{secrets.token_hex(16)}"}

    def reject(self,grant_request_id:str):
        req=self.requests[grant_request_id]
        req.status="REJECTED"
