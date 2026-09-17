#!/usr/bin/env python3
"""validate_qp_proof.py — run the full QP proof cycle and prove it works.

Exit code 0 = it works. Non-zero = it doesn't.
No human judgment. No "I think it works". Just the script result.
"""
import sys
import os
import json
import time
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, "/home/ubuntu/qprivately")
sys.path.insert(0, os.path.join(ROOT, ".."))

from acom.canonical import canonical, sha256_hex, obj_id
from acom.objects import make_claim, make_evidence
from acom.gates import execute
from acom.receipts import transition, verify_receipt, settle
from acom.store import Store


def log_result(test_name, passed, details=None):
    run_id = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    entry = {
        "run_id": run_id,
        "test": test_name,
        "passed": passed,
        "timestamp": time.time(),
    }
    if details:
        entry["details"] = details
    os.makedirs(os.path.join(ROOT, "..", "runs"), exist_ok=True)
    with open(os.path.join(ROOT, "..", "runs", "qp-proof-validation.jsonl"), "a") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")


def test_full_qp_proof_cycle():
    """Full cycle: claim → evidence → gates → receipt → verify."""
    
    # 1. Define claim
    claim = make_claim(
        statement="HBM demand exceeds supply",
        domain="semiconductors.memory",
        result="UNKNOWN"
    )
    assert claim["id"], "claim must have id"
    assert claim["result"] == "UNKNOWN", "claim must start UNKNOWN"
    
    # 2. Collect evidence
    ev1 = make_evidence(
        metric="qualified_hbm_supply",
        value=102,
        unit="normalized_capacity",
        as_of="2026-09-17",
        source={"class": "industry_data", "source_id": "trendforce-q3",
                "artifact_hash": "sha256:aaa111"}
    )
    ev2 = make_evidence(
        metric="hbm_demand_forecast",
        value=150,
        unit="normalized_capacity",
        as_of="2026-09-17",
        source={"class": "company_guidance", "source_id": "sk-hynix-q3",
                "artifact_hash": "sha256:bbb222"}
    )
    assert ev1["id"], "evidence must have id"
    assert ev2["id"], "evidence must have id"
    assert ev1["id"] != ev2["id"], "evidence ids must be unique"
    
    # 3. Execute gates
    gate1 = execute("two-sources-v1", {"evidence": [ev1, ev2]})
    assert gate1["result"] == "PASS", f"two-sources must PASS, got {gate1['result']}"
    
    gate2 = execute("evidence-fresh-v1", {"evidence": [ev1, ev2]})
    assert gate2["result"] == "PASS", f"evidence-fresh must PASS, got {gate2['result']}"
    
    gate3 = execute("no-duplicate-v1", {"evidence": [ev1, ev2]})
    assert gate3["result"] == "PASS", f"no-duplicate must PASS, got {gate3['result']}"
    
    # 4. Resolve claim
    claim["result"] = "TRUE"  # supply(102) < demand(150)
    
    gate4 = execute("claim-resolved-v1", {"claim": claim, "evidence": [ev1, ev2]})
    assert gate4["result"] == "PASS", f"claim-resolved must PASS, got {gate4['result']}"
    
    # 5. Create receipt
    receipt = transition(
        state_before={"cursor": 0, "event_root": "", "state_root": ""},
        proposal=claim,
        evidence=[ev1, ev2],
        gate_ids=["two-sources-v1", "evidence-fresh-v1", "no-duplicate-v1", "claim-resolved-v1"],
        run={"worker": "test-runner", "tokens": 0, "cost": 0.0},
        proof_level=7,
        apply=lambda state, proposal, evidence: {
            **state,
            "cursor": state["cursor"] + 1,
            "hbm_gap": "RESOLVED"
        }
    )
    
    assert receipt["id"], "receipt must have id"
    assert receipt["passed"] is True, "receipt must pass"
    assert receipt["proof_level"] == 7, "proof level must be 7"
    assert len(receipt["gates"]) == 4, "must have 4 gates"
    assert all(g["result"] == "PASS" for g in receipt["gates"]), "all gates must PASS"
    
    # 6. Verify receipt
    v = verify_receipt(receipt)
    assert v["ok"] is True, f"receipt must verify: {v['reason']}"
    
    # 7. Settle receipt
    s = settle(receipt, evidence=[ev1, ev2])
    assert s["ok"] is True, f"receipt must settle: {s['reason']}"
    
    return {
        "claim_id": claim["id"],
        "receipt_id": receipt["id"],
        "passed": receipt["passed"],
        "gates_passed": sum(1 for g in receipt["gates"] if g["result"] == "PASS"),
        "gates_total": len(receipt["gates"]),
    }


def test_tampered_receipt_fails():
    """Tampered receipt must fail verification."""
    claim = make_claim("test", "test", "TRUE")
    ev = make_evidence("m", 1, "u", "2026-09-17",
                       {"class": "other", "source_id": "s1", "artifact_hash": "sha256:xxx"})
    
    receipt = transition(
        state_before={"cursor": 0},
        proposal=claim,
        evidence=[ev],
        gate_ids=["evidence-fresh-v1"],
        run={"worker": "test"},
        proof_level=2,
    )
    
    # Verify original
    v1 = verify_receipt(receipt)
    assert v1["ok"] is True, "original must verify"
    
    # Tamper
    tampered = dict(receipt)
    tampered["id"] = "receipt:TAMPERED"
    
    v2 = verify_receipt(tampered)
    assert v2["ok"] is False, "tampered must fail"
    
    return {"original_ok": v1["ok"], "tampered_ok": v2["ok"]}


def test_store_append_only():
    """Store is append-only, chain verifies."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = f.name
    
    try:
        store = Store(path)
        
        # Append events
        for i in range(5):
            store.append("test", {"index": i})
        
        # Chain must verify
        assert store.verify_chain() is True, "chain must verify"
        
        # Cursor must advance
        assert store.cursor == 5, f"cursor must be 5, got {store.cursor}"
        
        # Event root must exist
        assert store.event_root, "event_root must exist"
        
        return {"events": 5, "cursor": store.cursor, "chain_ok": True}
    
    finally:
        os.unlink(path)


def test_canonical_deterministic():
    """Canonical serialization is deterministic."""
    obj = {"b": 2, "a": [1, 3], "c": {"nested": True}}
    
    b1 = canonical(obj)
    b2 = canonical(obj)
    b3 = canonical(obj)
    
    assert b1 == b2 == b3, "canonical must be deterministic"
    
    # Content-addressed ID
    id1 = obj_id("test", obj)
    id2 = obj_id("test", obj)
    assert id1 == id2, "obj_id must be deterministic"
    
    return {"deterministic": True, "id": id1}


def test_gate_unknown_fails():
    """Unknown gate ID must fail."""
    result = execute("nonexistent-gate-v1", {})
    assert result["result"] == "FAIL", "unknown gate must FAIL"
    assert "unknown" in result["proof"].lower(), "proof must mention unknown"
    
    return {"unknown_gate": "FAIL"}


def test_vault_fail_closed():
    """Vault must fail closed on wrong capability."""
    from agentcom.vault.store import Vault
    
    vault = Vault(os.path.expanduser("~/.qpbot/vault.json"))
    active = vault.find(kind="llm-inference", tier="paid")
    
    if not active:
        return {"vault": "no keys found"}
    
    try:
        vault.resolve(active[0]["name"], "wrong-tool", "w", "bad_cap")
        assert False, "must raise ValueError"
    except ValueError:
        pass  # expected
    
    return {"vault_fail_closed": True}


def main():
    tests = [
        ("full_qp_proof_cycle", test_full_qp_proof_cycle),
        ("tampered_receipt_fails", test_tampered_receipt_fails),
        ("store_append_only", test_store_append_only),
        ("canonical_deterministic", test_canonical_deterministic),
        ("gate_unknown_fails", test_gate_unknown_fails),
        ("vault_fail_closed", test_vault_fail_closed),
    ]
    
    results = []
    all_passed = True
    
    for name, fn in tests:
        try:
            details = fn()
            passed = True
            results.append({"test": name, "passed": True, "details": details})
            log_result(name, True, details)
            print(f"✓ {name}")
        except Exception as e:
            passed = False
            all_passed = False
            results.append({"test": name, "passed": False, "error": str(e)})
            log_result(name, False, {"error": str(e)})
            print(f"✗ {name}: {e}")
    
    # Summary
    total = len(results)
    passed_count = sum(1 for r in results if r["passed"])
    
    print(f"\n{'='*50}")
    print(f"QP PROOF VALIDATION: {passed_count}/{total} passed")
    print(f"{'='*50}")
    
    # Log summary
    log_result("summary", all_passed, {
        "total": total,
        "passed": passed_count,
        "failed": total - passed_count,
        "tests": results,
    })
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
