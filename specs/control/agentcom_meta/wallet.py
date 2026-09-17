from __future__ import annotations
from dataclasses import dataclass,asdict
from hashlib import sha256
import json,time
from typing import Protocol,Any

@dataclass(frozen=True)
class WalletPolicy:
    asset:str="USD"
    max_per_action:float=5.0
    max_daily:float=20.0
    allowed_capabilities:tuple[str,...]=("spend",)

@dataclass(frozen=True)
class GrantIntent:
    call_id:str
    contract_root:str
    subject:str
    capability:str
    value:float
    asset:str
    expires_at:float
    facts:dict[str,Any]

    @property
    def intent_id(self):
        raw=json.dumps(asdict(self),sort_keys=True,separators=(",",":"),default=str).encode();return "grant-intent:"+sha256(raw).hexdigest()

class AuthoritySigner(Protocol):
    def sign(self,intent:GrantIntent)->dict[str,Any]:...

class GrantBroker:
    """Wallet/grant boundary. It never stores a private key.

    The dashboard may approve an intent. A production signer (hardware wallet, vault,
    QP authority service) signs outside this process. Human approval and cryptographic
    authority remain distinct facts.
    """
    def __init__(self,policy:WalletPolicy,signer:AuthoritySigner|None=None):
        self.policy=policy;self.signer=signer;self.daily_used=0.0;self.approved:set[str]=set();self.grants:dict[str,dict[str,Any]]={}
    def propose(self,intent:GrantIntent)->dict[str,Any]:
        reasons=[]
        if intent.capability not in self.policy.allowed_capabilities:reasons.append("capability-not-allowed")
        if intent.asset!=self.policy.asset:reasons.append("asset-mismatch")
        if intent.value>self.policy.max_per_action:reasons.append("per-action-cap")
        if self.daily_used+intent.value>self.policy.max_daily:reasons.append("daily-cap")
        if intent.expires_at<=time.time():reasons.append("expired")
        return {"ok":not reasons,"reasons":reasons,"intent_id":intent.intent_id,"needs_human_approval":True}
    def approve(self,intent:GrantIntent)->str:
        p=self.propose(intent)
        if not p["ok"]:raise ValueError("grant-intent-policy:"+",".join(p["reasons"]))
        self.approved.add(intent.intent_id);return intent.intent_id
    def mint(self,intent:GrantIntent)->dict[str,Any]:
        if intent.intent_id not in self.approved:raise PermissionError("human-approval-is-not-recorded")
        if not self.signer:raise RuntimeError("production-signer-not-configured")
        grant=self.signer.sign(intent)
        if not grant.get("signature"):raise ValueError("unsigned-grant")
        self.grants[intent.intent_id]=grant;self.daily_used+=intent.value;return grant

class LocalTestSigner:
    """Deterministic test-only signer marker. Production code must inject a real QP signer."""
    def __init__(self,secret:str="TEST-ONLY"):
        self.secret=secret
    def sign(self,intent:GrantIntent)->dict[str,Any]:
        body=asdict(intent);raw=json.dumps(body,sort_keys=True,separators=(",",":"),default=str)
        sig=sha256((self.secret+raw).encode()).hexdigest()
        return {"kind":"TEST_ONLY_QP_GRANT","intent":body,"signature":sig,"warning":"not-production-cryptography"}

class ExactQPTestSigner:
    """Test harness around the exact reviewed QP Ed25519 grant code vendored in this bundle.

    Production should still inject a vault/hardware/authority-service signer. This class exists
    so conformance tests exercise the real QP grant format and signature verification.
    """
    def __init__(self,qp_root:str,secret:bytes=b"\x11"*32):
        self.qp_root=qp_root;self.secret=secret
    def sign(self,intent:GrantIntent)->dict[str,Any]:
        import sys
        from datetime import datetime,timezone
        if self.qp_root not in sys.path:sys.path.insert(0,self.qp_root)
        from acom import crypto
        _,pub=crypto.keypair(self.secret)
        expiry=datetime.fromtimestamp(intent.expires_at,tz=timezone.utc).isoformat()
        grant={
            "subject":pub.hex(),"capability":intent.capability,
            "constraints":{"max_value":intent.value,"asset":intent.asset,"max_calls":1},
            "predicates":[f"call_id == '{intent.call_id}'",f"contract_root == '{intent.contract_root}'"],
            "expiry":expiry,"intent_id":intent.intent_id,
        }
        grant["signature"]=crypto.sign_grant(self.secret,grant)
        return grant
