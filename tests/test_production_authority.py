import tempfile, threading
from pathlib import Path
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from agentcom.authority.grants import AuthorityAction, GrantAuthority, GrantStore, GrantVerifier, Grant
from agentcom.runtime.consequence import ConsequenceGate


def auth(tmp):
    return GrantAuthority(Ed25519PrivateKey.generate(), GrantStore(str(Path(tmp)/"grants.sqlite")))


def action(**kw):
    base=dict(capability="github.merge", subject="worker-1", resource="repo:prx0r/pq#1", params={"sha":"abc"}, task_id="t1", contract_root="r1", policy_version="v1")
    base.update(kw); return AuthorityAction(**base)


def test_issue_verify_consume_once():
    with tempfile.TemporaryDirectory() as d:
        a=auth(d); x=action(); g=a.issue(x, max_uses=1); a.verifier.verify(g,x); assert a.store.consume(g,x,a.verifier)==1
        with pytest.raises(ValueError): a.store.consume(g,x,a.verifier)

def test_action_tamper_rejected():
    with tempfile.TemporaryDirectory() as d:
        a=auth(d); x=action(); g=a.issue(x)
        with pytest.raises(ValueError): a.verifier.verify(g, action(params={"sha":"evil"}))

def test_signature_tamper_rejected():
    with tempfile.TemporaryDirectory() as d:
        a=auth(d); x=action(); g=a.issue(x)
        raw=g.to_dict(); raw["signature"]="AAAA"
        with pytest.raises(ValueError): a.verifier.verify(Grant.from_dict(raw),x)

def test_foreign_key_rejected():
    with tempfile.TemporaryDirectory() as d:
        trusted=auth(d); x=action(); other=GrantAuthority(Ed25519PrivateKey.generate(), GrantStore(str(Path(d)/"o.sqlite"))); g=other.issue(x)
        with pytest.raises(ValueError): trusted.verifier.verify(g,x)

def test_value_ceiling():
    with tempfile.TemporaryDirectory() as d:
        a=auth(d); x=action(capability="wallet.send", value_minor=100, currency="USD"); g=a.issue(x,max_value_minor=100)
        with pytest.raises(ValueError): a.verifier.verify(g, action(capability="wallet.send", value_minor=101, currency="USD"))

def test_expiry():
    with tempfile.TemporaryDirectory() as d:
        a=auth(d); x=action(); g=a.issue(x,ttl_s=1,now=100)
        with pytest.raises(ValueError): a.verifier.verify(g,x,now=101)

def test_revocation():
    with tempfile.TemporaryDirectory() as d:
        a=auth(d); x=action(); g=a.issue(x); a.store.revoke(g.grant_id)
        with pytest.raises(ValueError): a.store.consume(g,x,a.verifier)

def test_concurrent_single_use():
    with tempfile.TemporaryDirectory() as d:
        a=auth(d); x=action(); g=a.issue(x,max_uses=1); out=[]
        def run():
            try: out.append(a.store.consume(g,x,a.verifier))
            except Exception: out.append("err")
        ts=[threading.Thread(target=run) for _ in range(4)]
        [t.start() for t in ts]; [t.join() for t in ts]
        assert out.count(1)==1 and out.count("err")==3

def test_consequence_gate_consumes_before_effect():
    with tempfile.TemporaryDirectory() as d:
        a=auth(d); x=action(); g=a.issue(x); gate=ConsequenceGate(a.verifier,a.store); seen=[]
        r=gate.execute(x,g,effect=lambda: seen.append(a.store.status(g.grant_id)["uses"]) or "ok")
        assert r["ok"] and seen==[1]

def test_effect_failure_still_consumes():
    with tempfile.TemporaryDirectory() as d:
        a=auth(d); x=action(); g=a.issue(x); gate=ConsequenceGate(a.verifier,a.store)
        r=gate.execute(x,g,effect=lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        assert not r["ok"] and a.store.status(g.grant_id)["uses"]==1
