#!/usr/bin/env python3
"""test_ledger_real.py — test ledger with real data.

Exit code 0 = it works. Non-zero = it doesn't.
"""
import sys
import os
import json
import time
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.ledger import Ledger, canonical, obj_hash, settle_capture


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
    os.makedirs(os.path.join(ROOT, "runs"), exist_ok=True)
    with open(os.path.join(ROOT, "runs", "ledger-real-test.jsonl"), "a") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")


def test_ledger_append():
    """Ledger appends events."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = f.name
    
    try:
        ledger = Ledger(path)
        
        e1 = ledger.append("probe", {"target": "weak-creds-01", "banner": "web"})
        e2 = ledger.append("creds", {"target": "weak-creds-01", "user": "admin"})
        e3 = ledger.append("capture", {"target": "weak-creds-01", "flag": "XMCTF{...}"})
        
        assert ledger.cursor == 3
        assert e1["hash"], "event must have hash"
        assert e2["prev"] == e1["hash"], "chain must link"
        assert e3["prev"] == e2["hash"], "chain must link"
        
        return {"events": 3, "cursor": ledger.cursor, "chain_ok": True}
    finally:
        os.unlink(path)


def test_ledger_verify_chain():
    """Ledger chain verification works."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = f.name
    
    try:
        ledger = Ledger(path)
        for i in range(10):
            ledger.append("test", {"index": i})
        
        assert ledger.verify_chain() is True, "chain must verify"
        
        return {"events": 10, "chain_ok": True}
    finally:
        os.unlink(path)


def test_ledger_tamper_detection():
    """Ledger detects tampering."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = f.name
    
    try:
        ledger = Ledger(path)
        for i in range(5):
            ledger.append("test", {"index": i})
        
        # Tamper
        with open(path, "a") as f:
            f.write(json.dumps({
                "seq": 999, "type": "evil", "payload": {},
                "prev": "x", "hash": "y", "ts": 0
            }) + "\n")
        
        ledger2 = Ledger(path)
        assert ledger2.verify_chain() is False, "tampered chain must fail"
        
        return {"tamper_detected": True}
    finally:
        os.unlink(path)


def test_settle_capture():
    """settle_capture produces valid receipt."""
    receipt = settle_capture(
        target_id="weak-creds-01",
        agent_id="red-01",
        flag_sha256="abc123def456",
        evidence_hashes=["hash1", "hash2"],
        ledger_cursor=5,
    )
    
    assert receipt["id"], "receipt must have id"
    assert receipt["target_id"] == "weak-creds-01"
    assert receipt["verdict"] == "CAPTURED"
    assert receipt["flag_sha256"] == "abc123def456"
    
    return {"receipt_id": receipt["id"][:16] + "..."}


def test_receipt_content_addressed():
    """Receipt IDs are content-addressed."""
    r1 = settle_capture("t", "a", "f", ["e1"], 1)
    r2 = settle_capture("t", "a", "f", ["e1"], 1)
    r3 = settle_capture("t", "a", "DIFFERENT", ["e1"], 1)
    
    assert r1["id"] == r2["id"], "same input must produce same id"
    assert r1["id"] != r3["id"], "different input must produce different id"
    
    return {"deterministic": True, "idempotent": True}


def test_canonical_serialization():
    """Canonical serialization is deterministic."""
    obj = {"b": 2, "a": [1, 3], "c": {"nested": True}}
    
    b1 = canonical(obj)
    b2 = canonical(obj)
    assert b1 == b2, "canonical must be deterministic"
    
    # Content-addressed ID
    id1 = obj_hash(obj)
    id2 = obj_hash(obj)
    assert id1 == id2, "obj_hash must be deterministic"
    
    return {"deterministic": True}


def test_full_cycle():
    """Full cycle: append → settle → verify."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = f.name
    
    try:
        ledger = Ledger(path)
        
        # Append evidence
        e1 = ledger.append("probe", {"target": "t1", "banner": "web"})
        e2 = ledger.append("creds", {"target": "t1", "user": "admin"})
        
        # Settle capture
        receipt = settle_capture(
            target_id="t1",
            agent_id="red-01",
            flag_sha256="abc123",
            evidence_hashes=[e1["hash"], e2["hash"]],
            ledger_cursor=ledger.cursor,
        )
        
        # Verify chain
        assert ledger.verify_chain() is True, "chain must verify"
        
        # Verify receipt has all fields
        assert receipt["id"]
        assert receipt["target_id"] == "t1"
        assert receipt["verdict"] == "CAPTURED"
        
        return {
            "events": 2,
            "receipt_id": receipt["id"][:16] + "...",
            "chain_ok": True,
        }
    finally:
        os.unlink(path)


def main():
    tests = [
        ("ledger_append", test_ledger_append),
        ("ledger_verify_chain", test_ledger_verify_chain),
        ("ledger_tamper_detection", test_ledger_tamper_detection),
        ("settle_capture", test_settle_capture),
        ("receipt_content_addressed", test_receipt_content_addressed),
        ("canonical_serialization", test_canonical_serialization),
        ("full_cycle", test_full_cycle),
    ]
    
    all_passed = True
    for name, fn in tests:
        try:
            details = fn()
            log_result(name, True, details)
            print(f"✓ {name}")
        except Exception as e:
            all_passed = False
            log_result(name, False, {"error": str(e)})
            print(f"✗ {name}: {e}")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
