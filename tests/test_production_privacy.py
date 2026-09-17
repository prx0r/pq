import tempfile, json
from pathlib import Path
import pytest
from cryptography.fernet import Fernet

from agentcom.approvals.email_tokens import ApprovalTokenStore
from agentcom.htasks.queue import HTask, HQueue
from agentcom.runtime.providers import ProviderConfig, ProviderRegistry, build_chat_request, inspect_request
from agentcom.runtime.pi_acp import PiRuntimeConfig
from agentcom.vault.broker import VaultBroker


class FakeVault:
    def __init__(self):
        self.fernet=Fernet(Fernet.generate_key()); self.secrets={}; self.calls=[]
    def store(self,name,value,allowed_tools,allowed_workers,scope="",ttl_s=3600,max_uses=0,kind="other",tier="unpaid",active=True,**kw):
        self.secrets[name]={"cipher":self.fernet.encrypt(value.encode()).decode(),"allowed_tools":allowed_tools,"allowed_workers":allowed_workers,"scope":scope,"capability":"CAP-SECRET","active":active,"kind":kind,"tier":tier,"expires":10**12,"max_uses":max_uses,"uses":0,"usage":{},"rate_limit":{},"model":"","provider":""}; return {"name":name,"stored":True}
    def find(self,kind="",tier="",provider=""):
        return [{"name":n,"kind":s["kind"],"tier":s["tier"],"capability":s["capability"],"usage":{},"rate_limit":{},"provider":"","model":""} for n,s in self.secrets.items() if (not kind or s["kind"]==kind) and (not tier or s["tier"]==tier)]
    def credential_available(self,name): return bool(self.secrets.get(name,{}).get("active"))
    def resolve(self,name,tool,worker,capability,scope=""):
        s=self.secrets[name]
        if capability!=s["capability"]: raise ValueError("cap")
        if tool not in s["allowed_tools"] or worker not in s["allowed_workers"]: raise ValueError("grant")
        self.calls.append((name,tool,worker)); return self.fernet.decrypt(s["cipher"].encode()).decode()


def test_model_view_hides_capability():
    v=FakeVault(); v.store("k","secret",["tool"],["w"],kind="llm-inference",tier="paid"); view=VaultBroker(v).model_view(kind="llm-inference")
    assert view[0]["available"] and "capability" not in view[0]

def test_broker_resolves_only_inside_callback():
    v=FakeVault(); v.store("k","secret",["tool"],["w"]); b=VaultBroker(v)
    assert b.with_secret("k",tool="tool",worker="w",callback=lambda s:s.upper())=="SECRET"

def test_quarantine_inactive():
    v=FakeVault(); b=VaultBroker(v); r=b.quarantine("found","secret",kind="service"); assert not v.credential_available(r["name"])

def test_promote_gets_fresh_active_record():
    v=FakeVault(); b=VaultBroker(v); q=b.quarantine("found","secret"); p=b.promote(q["name"],allowed_tools=["x"],allowed_workers=["w"]); assert p["name"].startswith("approved:") and v.credential_available(p["name"])

def test_htask_binding_tamper_detected():
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/"q.json"; q=HQueue(); t=HTask("1","authority","approve",action={"amount":10}); q.emit(t); q.save(str(p)); raw=json.loads(p.read_text()); raw[0]["action"]["amount"]=99; p.write_text(json.dumps(raw))
        with pytest.raises(ValueError): HQueue.load(str(p))

def test_htask_expiry_denies():
    t=HTask("1","confirm","approve",lease_s=1,safe_default="deny"); t.expire(t.deadline); assert t.answer["value"]=="deny"

def test_secret_htask_cannot_answer():
    t=HTask("1","secret","paste key"); t.display();
    with pytest.raises(ValueError): t.answer_task("secret")

def test_email_token_one_time():
    with tempfile.TemporaryDirectory() as d:
        s=ApprovalTokenStore(str(Path(d)/"a.sqlite")); tok=s.create("digest","user",ttl_s=10,now=100); assert s.claim(tok,now=101)["action_digest"]=="digest"
        with pytest.raises(ValueError): s.claim(tok,now=102)

def test_email_token_expiry():
    with tempfile.TemporaryDirectory() as d:
        s=ApprovalTokenStore(str(Path(d)/"a.sqlite")); tok=s.create("digest","user",ttl_s=1,now=100)
        with pytest.raises(ValueError): s.claim(tok,now=101)

def test_provider_manual_selection_no_fallback():
    r=ProviderRegistry({"p":ProviderConfig("p","https://example.test/v1","m")}); assert r.get("p").model=="m"
    with pytest.raises(KeyError): r.get("missing")

def test_request_inspector_redacts_auth():
    c=ProviderConfig("p","https://example.test/v1","m",require_tee=True); body=build_chat_request(c,[{"role":"user","content":"hi"}],system_prompt="s"); x=inspect_request(c,body,headers={"Authorization":"Bearer secret","X-Test":"ok"}); assert x["headers"]["Authorization"]=="[REDACTED]" and x["headers"]["X-Test"]=="ok" and x["privacy"]["require_tee"]

def test_pi_requires_explicit_model():
    with pytest.raises(ValueError): PiRuntimeConfig(model="").validate()
