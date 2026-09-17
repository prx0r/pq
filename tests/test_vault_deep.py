"""Vault deep tests — full capture pipeline, classifier coverage, cost math.

Exercises the vault's secret lifecycle, key classification edge cases,
and the tracker's cost calculation for all models.
"""
from __future__ import annotations

import json
import tempfile
import os

import pytest

from agentcom.vault.store import Vault
from agentcom.vault.tracker import cost_minor, PRICING, track


def _store_and_get_cap(v, name="k", value="val", tools=None, workers=None, **kw):
    """Helper: store a secret and return the capability token for resolve."""
    result = v.store(name, value, tools or ["t"], workers or ["w"], **kw)
    return v.secrets[name]["capability"]


# ── Cost calculation for all models ────────────────────────────────────

def test_cost_muse_spark():
    c = cost_minor("muse-spark-1.3-contributor", 1_000_000, 1_000_000)
    assert c == 30

def test_cost_mimo_v25():
    c = cost_minor("mimo-v2.5", 1_000_000, 1_000_000)
    assert c == 42

def test_cost_mimo_v25_pro():
    c = cost_minor("mimo-v2.5-pro", 1_000_000, 1_000_000)
    assert c == 130

def test_cost_deepseek_v4_flash():
    c = cost_minor("deepseek-v4-flash", 1_000_000, 1_000_000)
    assert c == 75

def test_cost_deepseek_v4_pro():
    c = cost_minor("deepseek-v4-pro", 1_000_000, 1_000_000)
    assert c == 130

def test_cost_glm():
    c = cost_minor("glm-5.3-flash", 1_000_000, 1_000_000)
    assert c == 65

def test_cost_qwen():
    c = cost_minor("qwen3.7-plus", 1_000_000, 1_000_000)
    assert c == 200

def test_cost_kimi():
    c = cost_minor("kimi-k2.6", 1_000_000, 1_000_000)
    assert c == 495

def test_cost_hy3():
    c = cost_minor("hy3", 1_000_000, 1_000_000)
    assert c == 72

def test_cost_unknown_model():
    c = cost_minor("nonexistent-model", 1000, 1000)
    assert c == 0

def test_cost_zero_tokens():
    c = cost_minor("mimo-v2.5", 0, 0)
    assert c == 0

def test_cost_small_tokens():
    c = cost_minor("mimo-v2.5", 1000, 1000)
    assert c == 0

def test_cost_100k_tokens():
    c = cost_minor("mimo-v2.5", 100_000, 100_000)
    assert c == 4

def test_all_pricing_models_have_entries():
    for model in PRICING:
        assert "input" in PRICING[model]
        assert "output" in PRICING[model]
        assert "monthly_cap_minor" in PRICING[model]


# ── Vault full capture pipeline ────────────────────────────────────────

def test_vault_store_resolve_cycle():
    with tempfile.TemporaryDirectory() as d:
        v = Vault(os.path.join(d, "vault.json"))
        cap = _store_and_get_cap(v, "test-key", "supersecret",
                                 ["tool1"], ["worker1"])
        val = v.resolve("test-key", "tool1", "worker1", cap)
        assert val == "supersecret"

def test_vault_wrong_tool_rejects():
    with tempfile.TemporaryDirectory() as d:
        v = Vault(os.path.join(d, "vault.json"))
        cap = _store_and_get_cap(v)
        with pytest.raises(ValueError, match="not granted"):
            v.resolve("k", "wrong-tool", "w", cap)

def test_vault_wrong_worker_rejects():
    with tempfile.TemporaryDirectory() as d:
        v = Vault(os.path.join(d, "vault.json"))
        cap = _store_and_get_cap(v)
        with pytest.raises(ValueError, match="not granted"):
            v.resolve("k", "t", "wrong-worker", cap)

def test_vault_wrong_capability_rejects():
    with tempfile.TemporaryDirectory() as d:
        v = Vault(os.path.join(d, "vault.json"))
        _store_and_get_cap(v)
        with pytest.raises(ValueError, match="capability mismatch"):
            v.resolve("k", "t", "w", "WRONG-CAP")

def test_vault_expiry_blocks():
    with tempfile.TemporaryDirectory() as d:
        v = Vault(os.path.join(d, "vault.json"))
        cap = _store_and_get_cap(v, ttl_s=0)
        with pytest.raises(ValueError, match="expired"):
            v.resolve("k", "t", "w", cap)

def test_vault_max_uses_blocks():
    with tempfile.TemporaryDirectory() as d:
        v = Vault(os.path.join(d, "vault.json"))
        cap = _store_and_get_cap(v, max_uses=1)
        v.resolve("k", "t", "w", cap)  # uses=1
        with pytest.raises(ValueError, match="usage cap"):
            v.resolve("k", "t", "w", cap)  # uses=2, exhausted

def test_vault_revoked_blocks():
    with tempfile.TemporaryDirectory() as d:
        v = Vault(os.path.join(d, "vault.json"))
        cap = _store_and_get_cap(v)
        v.revoke("k")
        with pytest.raises(ValueError):
            v.resolve("k", "t", "w", cap)

def test_vault_inactive_blocks():
    with tempfile.TemporaryDirectory() as d:
        v = Vault(os.path.join(d, "vault.json"))
        cap = _store_and_get_cap(v)
        v.set_active("k", False)
        with pytest.raises(ValueError, match="inactive"):
            v.resolve("k", "t", "w", cap)

def test_vault_find_by_kind():
    with tempfile.TemporaryDirectory() as d:
        v = Vault(os.path.join(d, "vault.json"))
        v.store("llm-key", "key123", ["t"], ["w"], kind="llm-inference", tier="paid")
        v.store("other-key", "key456", ["t"], ["w"], kind="service", tier="unpaid")
        found = v.find(kind="llm-inference")
        assert len(found) == 1
        assert found[0]["name"] == "llm-key"

def test_vault_find_by_tier():
    with tempfile.TemporaryDirectory() as d:
        v = Vault(os.path.join(d, "vault.json"))
        v.store("paid-key", "v1", ["t"], ["w"], tier="paid")
        v.store("free-key", "v2", ["t"], ["w"], tier="unpaid")
        found = v.find(tier="paid")
        assert len(found) == 1

def test_vault_usage_tracking():
    with tempfile.TemporaryDirectory() as d:
        v = Vault(os.path.join(d, "vault.json"))
        v.store("k", "val", ["t"], ["w"], kind="llm-inference", tier="paid")
        v.record_usage("k", tokens_in=100, tokens_out=50, cost_minor=5)
        v.record_usage("k", tokens_in=200, tokens_out=100, cost_minor=10)
        s = v.usage_summary()
        assert s["totals"]["tokens_in"] == 300
        assert s["totals"]["tokens_out"] == 150
        assert s["totals"]["cost_minor"] == 15

def test_vault_overwrite_upsert():
    with tempfile.TemporaryDirectory() as d:
        v = Vault(os.path.join(d, "vault.json"))
        _store_and_get_cap(v, value="first")
        cap2 = _store_and_get_cap(v, value="second")
        val = v.resolve("k", "t", "w", cap2)
        assert val == "second"


# ── Tracker integration ────────────────────────────────────────────────

def test_track_extracts_chat_usage():
    with tempfile.TemporaryDirectory() as d:
        v = Vault(os.path.join(d, "vault.json"))
        v.store("k", "val", ["t"], ["w"], kind="llm-inference", tier="paid")
        resp = {"model": "mimo-v2.5",
                "usage": {"prompt_tokens": 1000, "completion_tokens": 500}}
        entry = track(v, "k", resp)
        assert entry["tokens_in"] == 1000
        assert entry["tokens_out"] == 500
        assert entry["model"] == "mimo-v2.5"

def test_track_extracts_responses_usage():
    with tempfile.TemporaryDirectory() as d:
        v = Vault(os.path.join(d, "vault.json"))
        v.store("k", "val", ["t"], ["w"], kind="llm-inference", tier="paid")
        resp = {"model": "muse-spark-1.3-contributor",
                "usage": {"input_tokens": 2000, "output_tokens": 1000}}
        entry = track(v, "k", resp)
        assert entry["tokens_in"] == 2000
        assert entry["tokens_out"] == 1000

def test_track_missing_usage():
    with tempfile.TemporaryDirectory() as d:
        v = Vault(os.path.join(d, "vault.json"))
        v.store("k", "val", ["t"], ["w"], kind="llm-inference", tier="paid")
        entry = track(v, "k", {"model": "mimo-v2.5"})
        assert entry["tokens_in"] == 0
        assert entry["tokens_out"] == 0
        assert entry["cost_minor"] == 0

def test_track_writes_jsonl():
    with tempfile.TemporaryDirectory() as d:
        v = Vault(os.path.join(d, "vault.json"))
        v.store("k", "val", ["t"], ["w"], kind="llm-inference", tier="paid")
        log_path = os.path.join(d, "usage.jsonl")
        resp = {"model": "mimo-v2.5",
                "usage": {"prompt_tokens": 100, "completion_tokens": 50}}
        track(v, "k", resp, log_path=log_path)
        with open(log_path) as f:
            lines = [l.strip() for l in f if l.strip()]
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["name"] == "k"
        assert entry["model"] == "mimo-v2.5"
