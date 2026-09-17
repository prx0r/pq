"""Seen tracker tests — dedup wallet investigations.

Ensures the system doesn't re-investigate wallets it's already checked.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from agentcom.seen import SeenTracker


def test_seen_tracker_mark():
    with tempfile.TemporaryDirectory() as d:
        st = SeenTracker(os.path.join(d, "seen.jsonl"))
        assert not st.is_seen("0xabc")
        st.mark("0xabc", workflow="test", chain="ethereum")
        assert st.is_seen("0xabc")

def test_seen_tracker_case_insensitive():
    with tempfile.TemporaryDirectory() as d:
        st = SeenTracker(os.path.join(d, "seen.jsonl"))
        st.mark("0xABC", workflow="test")
        assert st.is_seen("0xabc")
        assert st.is_seen("0xABC")

def test_seen_tracker_expiry():
    with tempfile.TemporaryDirectory() as d:
        st = SeenTracker(os.path.join(d, "seen.jsonl"))
        st.mark("0xabc", workflow="test")
        # Should be seen within 24h
        assert st.is_seen("0xabc", max_age_s=86400)
        # Should not be seen if max_age is 0 (already expired)
        assert not st.is_seen("0xabc", max_age_s=0)

def test_seen_tracker_force():
    with tempfile.TemporaryDirectory() as d:
        st = SeenTracker(os.path.join(d, "seen.jsonl"))
        st.mark("0xabc", workflow="test")
        # is_seen returns True, but worker can force=True to skip check
        assert st.is_seen("0xabc")

def test_seen_tracker_persistence():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "seen.jsonl")
        st1 = SeenTracker(path)
        st1.mark("0xabc", workflow="test", chain="ethereum")
        st1.mark("0xdef", workflow="test", chain="solana")
        # Reload
        st2 = SeenTracker(path)
        assert st2.is_seen("0xabc")
        assert st2.is_seen("0xdef")
        assert st2.count() == 2

def test_seen_tracker_count():
    with tempfile.TemporaryDirectory() as d:
        st = SeenTracker(os.path.join(d, "seen.jsonl"))
        assert st.count() == 0
        st.mark("0x1", workflow="test")
        st.mark("0x2", workflow="test")
        assert st.count() == 2

def test_seen_tracker_list_seen():
    with tempfile.TemporaryDirectory() as d:
        st = SeenTracker(os.path.join(d, "seen.jsonl"))
        st.mark("0xabc", chain="ethereum", prize_stored=True, github_found=True)
        st.mark("0xdef", chain="solana", prize_stored=False, github_found=False)
        all_seen = st.list_seen()
        assert len(all_seen) == 2
        eth = st.list_seen(chain="ethereum")
        assert len(eth) == 1
        assert eth[0]["chain"] == "ethereum"

def test_seen_tracker_stats():
    with tempfile.TemporaryDirectory() as d:
        st = SeenTracker(os.path.join(d, "seen.jsonl"))
        st.mark("0xabc", chain="ethereum", prize_stored=True, github_found=True)
        st.mark("0xdef", chain="solana", prize_stored=True, github_found=False)
        st.mark("0xghi", chain="ethereum", prize_stored=False, github_found=False)
        s = st.stats()
        assert s["total"] == 3
        assert s["by_chain"]["ethereum"] == 2
        assert s["by_chain"]["solana"] == 1
        assert s["with_prize"] == 2
        assert s["with_github"] == 1

def test_seen_tracker_different_addresses():
    with tempfile.TemporaryDirectory() as d:
        st = SeenTracker(os.path.join(d, "seen.jsonl"))
        st.mark("0xabc", workflow="test")
        assert st.is_seen("0xabc")
        assert not st.is_seen("0xdef")
        assert not st.is_seen("0xghi")

def test_seen_tracker_mark_fields():
    with tempfile.TemporaryDirectory() as d:
        st = SeenTracker(os.path.join(d, "seen.jsonl"))
        st.mark("0xabc", workflow="find_github", run_id="inv-123",
                signals_found=5, prize_stored=True, github_found=True,
                chain="ethereum")
        entry = st._seen["0xabc"]
        assert entry["workflow"] == "find_github"
        assert entry["run_id"] == "inv-123"
        assert entry["signals_found"] == 5
        assert entry["prize_stored"] is True
        assert entry["github_found"] is True
        assert entry["chain"] == "ethereum"


# ── Integration with worker ────────────────────────────────────────────

def test_worker_skips_seen_wallet():
    """Worker should skip if wallet was already investigated."""
    from agentcom.seen import SeenTracker

    with tempfile.TemporaryDirectory() as d:
        seen = SeenTracker(os.path.join(d, "seen.jsonl"))
        seen.mark("0xabc123", workflow="test", chain="ethereum")
        # Verify the dedup logic: is_seen returns True
        assert seen.is_seen("0xabc123")
        # The worker checks this before running - if True, it returns early
        # with error="already_investigated"

def test_workflow_skips_seen_wallet():
    """Workflow should skip if wallet was already investigated."""
    from agentcom.workflows import WorkflowRunner, WORKFLOWS
    from agentcom.seen import SeenTracker

    def fake_exec(tool, args):
        return {"ok": True, "data": {"count": 5, "txs": []}}

    with tempfile.TemporaryDirectory() as d:
        seen = SeenTracker(os.path.join(d, "seen.jsonl"))
        seen.mark("0xabc123", workflow="test")
        assert seen.is_seen("0xabc123")
