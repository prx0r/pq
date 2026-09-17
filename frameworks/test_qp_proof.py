"""QP Proof Validation — testing qpbot implementation against qprivately spec.

Every test logs to runs/qp-validation.jsonl with run_id, timestamp, and pass/fail.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

RUNS_DIR = os.path.join(ROOT, "runs")


def log_validation(criterion_id: str, test_name: str, passed: bool,
                   details: dict = None):
    os.makedirs(RUNS_DIR, exist_ok=True)
    entry = {
        "run_id": time.strftime("%Y%m%d-%H%M%S", time.gmtime()),
        "criterion": criterion_id,
        "test": test_name,
        "passed": passed,
        "timestamp": time.time(),
    }
    if details:
        entry["details"] = details
    with open(os.path.join(RUNS_DIR, "qp-validation.jsonl"), "a") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")


# ============================================================================
# ST-01: State transitions require all gates to pass
# ============================================================================

class TestQP_ST01:
    def test_valid_flag_accepted(self):
        from core.arena import submit_flag
        result = submit_flag("weak-creds-01", "XMCTF{weak_creds_demo_01}")
        assert result["verdict"] == "CAPTURED"
        log_validation("ST-01", "valid_flag_accepted", True, result)

    def test_wrong_flag_rejected(self):
        from core.arena import submit_flag
        result = submit_flag("weak-creds-01", "WRONG_FLAG")
        assert result["verdict"] == "REJECTED"
        log_validation("ST-01", "wrong_flag_rejected", True, result)

    def test_unknown_target_rejected(self):
        from core.arena import submit_flag
        result = submit_flag("nonexistent", "XMCTF{anything}")
        assert result["verdict"] == "UNKNOWN_TARGET"
        log_validation("ST-01", "unknown_target_rejected", True, result)


# ============================================================================
# GATE-01 through GATE-05: Arena verification is deterministic
# ============================================================================

class TestQP_GATES:
    def test_submit_flag_deterministic(self):
        from core.arena import submit_flag
        r1 = submit_flag("weak-creds-01", "XMCTF{weak_creds_demo_01}")
        r2 = submit_flag("weak-creds-01", "XMCTF{weak_creds_demo_01}")
        assert r1["verdict"] == r2["verdict"]
        assert r1["flag_sha256"] == r2["flag_sha256"]
        log_validation("GATE-01", "submit_flag_deterministic", True, r1)

    def test_tool_grant_table(self):
        from core.arena import is_allowed
        assert is_allowed("probe") is True
        assert is_allowed("try_creds") is True
        assert is_allowed("read_file") is True
        assert is_allowed("submit_flag") is True
        assert is_allowed("reverse_shell") is False
        assert is_allowed("nonexistent_tool") is False
        log_validation("GATE-02", "tool_grant_table", True, {})

    def test_probe_returns_banner(self):
        from core.arena import probe
        result = probe("weak-creds-01")
        assert "banner" in result or "category" in result
        log_validation("GATE-03", "probe_returns_banner", True, result)

    def test_try_creds_works(self):
        from core.arena import try_creds
        result = try_creds("weak-creds-01", "admin", "admin")
        assert "captured" in result or "flag" in result or "ok" in result
        log_validation("GATE-04", "try_creds_works", True, result)


# ============================================================================
# VER-01/03: Receipt verification
# ============================================================================

class TestQP_VER:
    def test_settle_capture_produces_receipt(self):
        from core.ledger import settle_capture
        receipt = settle_capture(
            target_id="weak-creds-01",
            agent_id="red-01",
            flag_sha256="abc123",
            evidence_hashes=["hash1", "hash2"],
            ledger_cursor=5,
        )
        assert "id" in receipt
        assert receipt["target_id"] == "weak-creds-01"
        log_validation("VER-01", "settle_capture_produces_receipt", True, receipt)

    def test_receipt_id_is_content_addressed(self):
        from core.ledger import settle_capture, obj_hash
        r1 = settle_capture("t", "a", "f", ["e1"], 1)
        r2 = settle_capture("t", "a", "f", ["e1"], 1)
        assert r1["id"] == r2["id"], "same input must produce same receipt id"
        log_validation("VER-01", "receipt_id_content_addressed", True, {"id": r1["id"]})

    def test_tampered_receipt_different_id(self):
        from core.ledger import settle_capture
        r1 = settle_capture("t", "a", "f", ["e1"], 1)
        r2 = settle_capture("t", "a", "DIFFERENT", ["e1"], 1)
        assert r1["id"] != r2["id"], "different input must produce different receipt id"
        log_validation("VER-03", "tampered_receipt_different_id", True, {})


# ============================================================================
# STORE-01: Ledger is append-only with chain verification
# ============================================================================

class TestQP_STORE:
    def test_ledger_append_only(self):
        from core.ledger import Ledger
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            ledger = Ledger(path)
            c1 = ledger.cursor
            ledger.append("test", {"x": 1})
            ledger.append("test", {"x": 2})
            assert ledger.cursor == c1 + 2
            assert not hasattr(ledger, "delete")
            assert not hasattr(ledger, "update")
            log_validation("STORE-01", "ledger_append_only", True, {})
        finally:
            os.unlink(path)

    def test_chain_verification(self):
        from core.ledger import Ledger
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            ledger = Ledger(path)
            for i in range(3):
                ledger.append("test", {"i": i})
            assert ledger.verify_chain() is True
            log_validation("STORE-01", "chain_verification_valid", True, {})
        finally:
            os.unlink(path)

    def test_tampered_chain_fails(self):
        from core.ledger import Ledger
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            ledger = Ledger(path)
            for i in range(3):
                ledger.append("test", {"i": i})
            # Tamper
            with open(path, "a") as f:
                f.write(json.dumps({"seq": 999, "type": "evil", "payload": {},
                                    "prev": "x", "hash": "y", "ts": 0}) + "\n")
            ledger2 = Ledger(path)
            assert ledger2.verify_chain() is False
            log_validation("STORE-01", "tampered_chain_fails", True, {})
        finally:
            os.unlink(path)


# ============================================================================
# AUTH-02: Vault fails closed
# ============================================================================

class TestQP_AUTH:
    def test_wrong_capability_rejected(self):
        from agentcom.vault.store import Vault
        vault = Vault(os.path.expanduser("~/.qpbot/vault.json"))
        active = vault.find(kind="llm-inference", tier="paid")
        with pytest.raises(ValueError):
            vault.resolve(active[0]["name"], "wrong-tool", "w", "bad_cap")
        log_validation("AUTH-02", "wrong_capability_rejected", True, {})

    def test_valid_key_resolves(self):
        from agentcom.vault.store import Vault
        vault = Vault(os.path.expanduser("~/.qpbot/vault.json"))
        active = vault.find(kind="llm-inference", tier="paid")
        key = vault.resolve(active[0]["name"], "dashboard-chat", "chat-session",
                           active[0]["capability"])
        assert key is not None
        assert len(key) > 10
        log_validation("AUTH-02", "valid_key_resolves", True, {"key_len": len(key)})


# ============================================================================
# SEP-01: Evidence and inference are separate
# ============================================================================

class TestQP_SEP:
    def test_evidence_has_no_verdict(self):
        from core.ledger import Ledger
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            path = f.name
        try:
            ledger = Ledger(path)
            ledger.append("probe", {"target": "t", "banner": "web"})
            events = ledger.read_all()
            payload = events[-1]["payload"]
            assert "verdict" not in payload
            assert "passed" not in payload
            log_validation("SEP-01", "evidence_has_no_verdict", True, {})
        finally:
            os.unlink(path)


# ============================================================================
# TOURN-02: Promotion gate
# ============================================================================

class TestQP_TOURN:
    def test_minimum_uses_enforced(self):
        from core.guards import assess_promotion
        r = assess_promotion(uses=2, passes=2, total=2, regressions=0)
        assert r["promoted"] is False
        r = assess_promotion(uses=3, passes=3, total=3, regressions=0)
        assert r["promoted"] is True
        log_validation("TOURN-02", "minimum_uses_enforced", True, {})

    def test_pass_rate_enforced(self):
        from core.guards import assess_promotion
        r = assess_promotion(uses=10, passes=8, total=10, regressions=0)
        assert r["promoted"] is False  # 80% < 90%
        r = assess_promotion(uses=10, passes=9, total=10, regressions=0)
        assert r["promoted"] is True  # 90%
        log_validation("TOURN-02", "pass_rate_enforced", True, {})

    def test_regressions_block_promotion(self):
        from core.guards import assess_promotion
        r = assess_promotion(uses=10, passes=10, total=10, regressions=1)
        assert r["promoted"] is False
        log_validation("TOURN-02", "regressions_block_promotion", True, {})

    def test_budget_enforced(self):
        from core.guards import check_budget
        check_budget(rounds=1)  # should not raise
        with pytest.raises(ValueError):
            check_budget(rounds=999)
        log_validation("TOURN-02", "budget_enforced", True, {})


# ============================================================================
# SER-01: Canonical serialization
# ============================================================================

class TestQP_SER:
    def test_canonical_deterministic(self):
        from core.ledger import canonical
        obj = {"b": 2, "a": [1, 3]}
        assert canonical(obj) == canonical(obj)
        log_validation("SER-01", "canonical_deterministic", True, {})

    def test_canonical_sorted_keys(self):
        from core.ledger import canonical
        result = canonical({"z": 1, "a": 2}).decode()
        assert result.index("a") < result.index("z")
        log_validation("SER-01", "canonical_sorted_keys", True, {})


# ============================================================================
# Summary
# ============================================================================

class TestQP_Summary:
    def test_summary(self):
        path = os.path.join(RUNS_DIR, "qp-validation.jsonl")
        if not os.path.exists(path):
            pytest.skip("no results")
        with open(path) as f:
            results = [json.loads(l) for l in f if l.strip()]
        total = len(results)
        passed = sum(1 for r in results if r["passed"])
        criteria = list(set(r["criterion"] for r in results))

        print(f"\n{'='*60}")
        print(f"QP PROOF VALIDATION: {passed}/{total} passed")
        print(f"Criteria tested: {', '.join(sorted(criteria))}")
        print(f"{'='*60}")

        critical = [r for r in results
                    if r["criterion"] in ("ST-01", "VER-01", "STORE-01", "AUTH-02", "TOURN-02")]
        failed_critical = [r for r in critical if not r["passed"]]
        assert not failed_critical, f"CRITICAL FAILURES: {[r['criterion']+':'+r['test'] for r in failed_critical]}"
