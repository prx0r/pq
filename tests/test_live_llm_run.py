"""Live LLM run — the only test in pq.

A test IS a logged LLM run, nothing else. It resolves a vault-held key,
calls the backend (default mimo-v2.5 on the OpenCode Go chat endpoint),
logs usage via the async logger to pq/runs/, and asserts a real reply.
Override the backend with PQ_MODEL (e.g. muse-spark-1.3-contributor once
the workspace opt-in lands).
"""
from __future__ import annotations

import os
import sys
import time
import urllib.error

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from agentcom.vault.asynclog import UsageLogger
from agentcom.vault.store import Vault
from agentcom.vault.tracker import cost_minor
from harness import call_api

BACKEND = os.environ.get("PQ_MODEL", "muse-spark-1.3-contributor")


def test_logged_llm_run():
    vault = Vault(os.path.expanduser("~/.qpbot/vault.json"))
    active = vault.find(kind="llm-inference", tier="paid")
    if not active:
        pytest.skip("no active LLM keys in vault")
    ordered = sorted(active,
                     key=lambda a: 0 if a.get("model") == BACKEND else 1)
    key = pick = None
    for cand in ordered:
        try:
            key = vault.resolve(cand["name"], "dashboard-chat",
                                "chat-session", cand["capability"])
            pick = cand
            break
        except ValueError:
            continue
    if key is None:
        pytest.skip("no usable LLM keys in vault (all spent/expired)")

    logger = UsageLogger(vault=vault,
                         log_path=os.path.join(ROOT, "runs", "llm-runs.jsonl"),
                         buffer_size=100, flush_interval_s=1)
    t0 = time.time()
    try:
        resp = call_api(key, [{"role": "user",
                               "content": "Reply with exactly: PQ_OK"}],
                        model=BACKEND)
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode()
        except Exception:
            pass
        if "DataPolicyError" in body or "opt in" in body:
            pytest.skip(f"{BACKEND} blocked: workspace opt-in pending")
        raise
    duration_ms = int((time.time() - t0) * 1000)

    usage = resp.get("usage", {})
    ti = usage.get("prompt_tokens", 0)
    to = usage.get("completion_tokens", 0)
    model = resp.get("model", BACKEND)
    text = (resp["choices"][0]["message"]["content"] or "")
    logger.log(pick["name"], model, tokens_in=ti, tokens_out=to,
               cost_minor=cost_minor(model, ti, to),
               duration_ms=duration_ms)
    logger.shutdown()

    assert text.strip(), f"empty reply from {BACKEND}"
    assert "PQ_OK" in text, f"unexpected reply: {text[:200]!r}"
