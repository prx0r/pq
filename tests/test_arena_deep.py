"""Arena deep tests — edge cases, attack vectors, and cross-module flows.

These exercise scenarios that qpbot's 56 unit tests don't cover:
ledger tampering, arena boundary conditions, grant table coverage,
and the full capture pipeline.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile

import pytest

from core.arena import (
    _FLAGS, _TARGETS, probe, try_creds, read_file, exploit_sqli_sim,
    submit_flag, flag_sha256, is_allowed, list_targets, list_packs,
    GRANTS, _sha256,
)
from core.ledger import Ledger, settle_capture, obj_hash
from core.guards import assess_promotion, check_budget, MAX_ROUNDS, MAX_EVIDENCE_EVENTS


# ── Arena boundary conditions ──────────────────────────────────────────

def test_unknown_target_returns_error():
    r = probe("nonexistent-01")
    assert r == {"ok": False, "error": "unknown-target"}

def test_unknown_target_try_creds():
    r = try_creds("nonexistent-01", "a", "b")
    assert r["ok"] is False

def test_unknown_target_read_file():
    r = read_file("nonexistent-01", "/flag.txt")
    assert r["ok"] is False

def test_unknown_target_sqli():
    r = exploit_sqli_sim("nonexistent-01", "' OR '1'='1")
    assert r["ok"] is False

def test_unknown_target_submit():
    r = submit_flag("nonexistent-01", "X")
    assert r["ok"] is False
    assert r["verdict"] == "UNKNOWN_TARGET"

def test_wrong_creds_reject():
    r = try_creds("weak-creds-01", "admin", "wrong")
    assert r["ok"] is True and r["captured"] is False

def test_wrong_path_denied():
    r = read_file("traversal-01", "/etc/passwd")
    assert r["ok"] is True and r["captured"] is False

def test_wrong_sqli_payload():
    r = exploit_sqli_sim("sqli-sim-01", "UNION SELECT *")
    assert r["ok"] is True and r["captured"] is False

def test_submit_wrong_flag():
    r = submit_flag("weak-creds-01", "XMCTF{wrong}")
    assert r["ok"] is False
    assert r["verdict"] == "REJECTED"

def test_submit_correct_flag():
    r = submit_flag("weak-creds-01", _FLAGS["weak-creds-01"])
    assert r["ok"] is True
    assert r["verdict"] == "CAPTURED"

def test_flag_sha256_matches():
    for tid, flag in _FLAGS.items():
        assert flag_sha256(tid) == hashlib.sha256(flag.encode()).hexdigest()

def test_all_targets_capturable():
    assert try_creds("weak-creds-01", "admin", "admin")["captured"]
    assert read_file("traversal-01", "../../flag.txt")["captured"]
    assert exploit_sqli_sim("sqli-sim-01", "' OR '1'='1")["captured"]

def test_list_packs_contains_demo():
    assert "demo" in list_packs()

def test_list_targets_has_3():
    targets = list_targets("demo")
    assert len(targets) == 3
    ids = {t["target_id"] for t in targets}
    assert ids == {"weak-creds-01", "traversal-01", "sqli-sim-01"}


# ── Grant table coverage ───────────────────────────────────────────────

def test_low_risk_tools_allowed():
    for name in ("probe", "try_creds", "read_file", "exploit_sqli_sim", "submit_flag"):
        assert is_allowed(name), f"{name} should be allowed"

def test_high_risk_tool_denied():
    assert not is_allowed("reverse_shell")

def test_unknown_tool_denied():
    assert not is_allowed("rm_rf")


# ── Ledger integrity and tampering ────────────────────────────────────

def test_ledger_append_and_verify():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "events.jsonl")
        L = Ledger(path)
        L.append("test", {"x": 1})
        L.append("test", {"x": 2})
        assert L.verify_chain()

def test_ledger_tamper_payload():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "events.jsonl")
        L = Ledger(path)
        L.append("test", {"x": 1})
        L.append("test", {"x": 2})
        # Tamper with the first event's payload
        events = L.read_all()
        events[0]["payload"]["x"] = 999
        with open(path, "w") as f:
            for e in events:
                f.write(json.dumps(e, sort_keys=True) + "\n")
        L2 = Ledger(path)
        assert not L2.verify_chain()

def test_ledger_tamper_hash():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "events.jsonl")
        L = Ledger(path)
        L.append("test", {"x": 1})
        L.append("test", {"x": 2})
        # Tamper with hash
        events = L.read_all()
        events[1]["hash"] = "0" * 64
        with open(path, "w") as f:
            for e in events:
                f.write(json.dumps(e, sort_keys=True) + "\n")
        assert not Ledger(path).verify_chain()

def test_ledger_tamper_prev_pointer():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "events.jsonl")
        L = Ledger(path)
        L.append("test", {"x": 1})
        L.append("test", {"x": 2})
        # Tamper with prev pointer
        events = L.read_all()
        events[1]["prev"] = "0" * 64
        with open(path, "w") as f:
            for e in events:
                f.write(json.dumps(e, sort_keys=True) + "\n")
        assert not Ledger(path).verify_chain()

def test_ledger_delete_event_breaks_chain():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "events.jsonl")
        L = Ledger(path)
        L.append("test", {"x": 1})
        L.append("test", {"x": 2})
        L.append("test", {"x": 3})
        # Delete middle event
        events = L.read_all()
        events.pop(1)
        with open(path, "w") as f:
            for e in events:
                f.write(json.dumps(e, sort_keys=True) + "\n")
        assert not Ledger(path).verify_chain()

def test_ledger_settle_capture():
    receipt = settle_capture("weak-creds-01", "agent-1", "abc123", ["h1"], 5)
    assert receipt["verdict"] == "CAPTURED"
    assert receipt["flag_sha256"] == "abc123"
    assert receipt["target_id"] == "weak-creds-01"
    assert receipt["agent_id"] == "agent-1"
    assert "id" in receipt

def test_ledger_empty_is_valid():
    with tempfile.TemporaryDirectory() as d:
        L = Ledger(os.path.join(d, "empty.jsonl"))
        assert L.verify_chain()
        assert L.read_all() == []


# ── Guards boundary conditions ─────────────────────────────────────────

def test_promotion_total_zero():
    r = assess_promotion(uses=0, passes=0, total=0, regressions=0)
    assert r["promoted"] is False
    assert r["pass_rate"] == 0.0

def test_promotion_exactly_at_boundary():
    r = assess_promotion(uses=3, passes=9, total=10, regressions=0)
    assert r["promoted"] is True

def test_promotion_just_below_uses():
    r = assess_promotion(uses=2, passes=10, total=10, regressions=0)
    assert r["promoted"] is False

def test_promotion_just_below_rate():
    r = assess_promotion(uses=3, passes=8, total=10, regressions=0)
    assert r["promoted"] is False
    assert r["pass_rate"] == 0.8

def test_promotion_has_regressions():
    r = assess_promotion(uses=5, passes=10, total=10, regressions=1)
    assert r["promoted"] is False

def test_budget_max_rounds():
    with pytest.raises(ValueError, match="rounds"):
        check_budget(MAX_ROUNDS + 1)

def test_budget_max_evidence():
    with pytest.raises(ValueError, match="evidence"):
        check_budget(1, MAX_EVIDENCE_EVENTS + 1)

def test_budget_at_limit_ok():
    check_budget(MAX_ROUNDS, MAX_EVIDENCE_EVENTS)
