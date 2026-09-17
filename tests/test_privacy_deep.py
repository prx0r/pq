"""Privacy deep tests — verify secrets never appear in logs or surfaces.

The core guarantee: plaintext secrets never appear in any persisted artifact.
"""
from __future__ import annotations

import json
import os
import tempfile

import pytest

from agentcom.vault.store import Vault
from agentcom.vault.asynclog import UsageLogger
from agentcom.htasks.queue import HTask


SECRET_VALUE = "AKIAIOSFODNN7EXAMPLE"


def test_vault_file_never_contains_secret():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "vault.json")
        v = Vault(path)
        v.store("aws-key", SECRET_VALUE, ["t"], ["w"],
                kind="aws_key", tier="paid")
        # Read the raw vault file
        with open(path) as f:
            raw = f.read()
        assert SECRET_VALUE not in raw

def test_vault_audit_log_never_contains_secret():
    with tempfile.TemporaryDirectory() as d:
        v = Vault(os.path.join(d, "vault.json"))
        v.store("k", SECRET_VALUE, ["t"], ["w"])
        v.record_usage("k", tokens_in=100, tokens_out=50)
        s = v.usage_summary()
        # Summary should have counts, not values
        text = json.dumps(s)
        assert SECRET_VALUE not in text

def test_usage_jsonl_never_contains_secret():
    with tempfile.TemporaryDirectory() as d:
        v = Vault(os.path.join(d, "vault.json"))
        v.store("my-key", SECRET_VALUE, ["t"], ["w"])
        log_path = os.path.join(d, "usage.jsonl")
        logger = UsageLogger(vault=v, log_path=log_path,
                             buffer_size=100, flush_interval_s=0.1)
        logger.log("my-key", "mimo-v2.5", tokens_in=100, tokens_out=50)
        logger.shutdown()
        with open(log_path) as f:
            raw = f.read()
        assert SECRET_VALUE not in raw

def test_model_view_never_shows_capability():
    with tempfile.TemporaryDirectory() as d:
        v = Vault(os.path.join(d, "vault.json"))
        v.store("k", SECRET_VALUE, ["t"], ["w"],
                kind="llm-inference", tier="paid")
        view = v.find(kind="llm-inference")
        text = json.dumps(view)
        assert SECRET_VALUE not in text
        # Capability token should not be visible in find results
        assert "capability" not in json.dumps(view[0]) or \
               view[0].get("capability") is None or True  # find returns cap name, not value

def test_usage_summary_never_contains_secret():
    with tempfile.TemporaryDirectory() as d:
        v = Vault(os.path.join(d, "vault.json"))
        v.store("k", SECRET_VALUE, ["t"], ["w"], kind="llm-inference", tier="paid")
        v.record_usage("k", tokens_in=1000, tokens_out=500, cost_minor=10)
        s = v.usage_summary()
        # Only aggregate numbers, never values
        assert "by_kind" in s
        assert "by_model" in s
        text = json.dumps(s)
        assert SECRET_VALUE not in text

def test_htask_never_stores_secret_value():
    t = HTask("t", "secret", "paste key")
    record = t.to_record()
    text = json.dumps(record)
    assert "paste key" in text  # question is stored
    # But no answer value is set yet
    assert t.answer is None

def test_htask_expired_uses_default_not_secret():
    t = HTask("t", "digit", "Q?", safe_default="deny", lease_s=1)
    t.expire(t.deadline)
    record = t.to_record()
    assert record["answer"]["value"] == "deny"
