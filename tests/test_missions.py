"""Multi-agent tests — missions, workers, dispatch, reporting.

Tests the full flow: main agent dispatches mission -> worker executes
-> results collected -> findings reported back.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from agentcom.missions import Mission, MissionControl
from agentcom.worker import run_worker


# ── Mission lifecycle ──────────────────────────────────────────────────

def test_mission_dispatch():
    with tempfile.TemporaryDirectory() as d:
        mc = MissionControl(os.path.join(d, "missions.jsonl"))
        m = mc.dispatch("find whale wallets on ETH")
        assert m.status == "queued"
        assert m.objective == "find whale wallets on ETH"
        assert m.id.startswith("m-")

def test_mission_start():
    with tempfile.TemporaryDirectory() as d:
        mc = MissionControl(os.path.join(d, "missions.jsonl"))
        m = mc.dispatch("test mission")
        mc.start(m.id, run_id="run-123")
        m2 = mc.get(m.id)
        assert m2.status == "running"
        assert m2.run_id == "run-123"

def test_mission_complete():
    with tempfile.TemporaryDirectory() as d:
        mc = MissionControl(os.path.join(d, "missions.jsonl"))
        m = mc.dispatch("test")
        mc.start(m.id)
        mc.complete(m.id, result={"ok": True}, findings=[{"tool": "eth_check"}],
                    tokens_in=100, tokens_out=50)
        m2 = mc.get(m.id)
        assert m2.status == "done"
        assert len(m2.findings) == 1
        assert m2.tokens_in == 100

def test_mission_fail():
    with tempfile.TemporaryDirectory() as d:
        mc = MissionControl(os.path.join(d, "missions.jsonl"))
        m = mc.dispatch("test")
        mc.start(m.id)
        mc.fail(m.id, "API timeout")
        m2 = mc.get(m.id)
        assert m2.status == "failed"
        assert m2.error == "API timeout"

def test_mission_list():
    with tempfile.TemporaryDirectory() as d:
        mc = MissionControl(os.path.join(d, "missions.jsonl"))
        mc.dispatch("mission 1")
        mc.dispatch("mission 2")
        mc.dispatch("mission 3")
        all_m = mc.list_missions()
        assert len(all_m) == 3

def test_mission_list_filter():
    with tempfile.TemporaryDirectory() as d:
        mc = MissionControl(os.path.join(d, "missions.jsonl"))
        m1 = mc.dispatch("done mission")
        m2 = mc.dispatch("running mission")
        mc.start(m2.id)
        mc.complete(m1.id, result={})
        done = mc.list_missions(status="done")
        assert len(done) == 1
        running = mc.list_missions(status="running")
        assert len(running) == 1

def test_mission_summary():
    with tempfile.TemporaryDirectory() as d:
        mc = MissionControl(os.path.join(d, "missions.jsonl"))
        m1 = mc.dispatch("a")
        m2 = mc.dispatch("b")
        mc.start(m1.id)
        mc.complete(m1.id, result={}, findings=[{"tool": "x"}, {"tool": "y"}])
        s = mc.summary()
        assert s["total"] == 2
        assert s["by_status"]["done"] == 1
        assert s["by_status"]["queued"] == 1
        assert s["total_findings"] == 2

def test_mission_persistence():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "missions.jsonl")
        mc1 = MissionControl(path)
        m = mc1.dispatch("persist test")
        mc1.start(m.id)
        # Reload
        mc2 = MissionControl(path)
        m2 = mc2.get(m.id)
        assert m2 is not None
        assert m2.status == "running"

def test_mission_event_log():
    with tempfile.TemporaryDirectory() as d:
        mc = MissionControl(os.path.join(d, "missions.jsonl"))
        m = mc.dispatch("event test")
        mc.start(m.id)
        mc.complete(m.id, result={})
        event_file = os.path.join(d, "missions.jsonl.events")
        assert os.path.exists(event_file)
        with open(event_file) as f:
            events = [json.loads(l) for l in f if l.strip()]
        assert len(events) == 3
        assert [e["event"] for e in events] == ["dispatched", "started", "completed"]

def test_mission_custom_id():
    with tempfile.TemporaryDirectory() as d:
        mc = MissionControl(os.path.join(d, "missions.jsonl"))
        m = mc.dispatch("custom id test", mission_id="my-mission-1")
        assert m.id == "my-mission-1"
        assert mc.get("my-mission-1") is not None

def test_mission_findings_accumulate():
    with tempfile.TemporaryDirectory() as d:
        mc = MissionControl(os.path.join(d, "missions.jsonl"))
        m = mc.dispatch("accumulate test")
        mc.start(m.id)
        mc.complete(m.id, result={},
                    findings=[{"tool": "eth_check", "data": {"ETH": 1.5}},
                              {"tool": "sol_check", "data": {"SOL": 100}},
                              {"tool": "classify", "data": {"kind": "eth_key"}}])
        m2 = mc.get(m.id)
        assert len(m2.findings) == 3


# ── Worker execution (live LLM, spends budget) ─────────────────────────

def test_worker_no_keys():
    """Worker with no vault keys should return error."""
    with tempfile.TemporaryDirectory() as d:
        # Create empty vault
        from agentcom.vault.store import Vault
        empty_vault = os.path.join(d, "vault.json")
        Vault(empty_vault)  # creates empty vault
        # Patch config
        import pqconfig as cfg
        old_path = cfg.vault_path()
        try:
            cfg._CONFIG = cfg._load() or {}
            cfg._CONFIG.setdefault("vault", {})["path"] = empty_vault
            result = run_worker("test objective", max_turns=2)
            assert result["ok"] is False
            assert "key" in result["error"].lower()
        finally:
            cfg._CONFIG["vault"]["path"] = old_path

def test_worker_basic():
    """Run a minimal worker mission. Spends LLM budget."""
    result = run_worker(
        "Check the balance of ETH address 0x0000000000000000000000000000000000000000",
        tools=["eth_check"],
        max_turns=3,
    )
    assert "run_id" in result
    assert "findings" in result
    assert "tools_used" in result
    assert "tokens_in" in result


# ── Dashboard API integration ──────────────────────────────────────────

def test_dashboard_mission_api_shape():
    """Verify the mission API returns correct JSON shape."""
    from agentcom.missions import MissionControl
    mc = MissionControl()
    data = mc.list_missions()
    assert isinstance(data, list)
    summary = mc.summary()
    assert "total" in summary
    assert "by_status" in summary


# ── End-to-end: dispatch -> worker -> collect ──────────────────────────

def test_e2e_dispatch_and_collect():
    """Full flow: dispatch mission, run worker, collect results."""
    with tempfile.TemporaryDirectory() as d:
        mc = MissionControl(os.path.join(d, "missions.jsonl"))
        m = mc.dispatch("check ETH balance of vitalik", tools=["eth_check"])
        assert m.status == "queued"

        # Simulate worker execution
        mc.start(m.id, run_id="test-run")
        assert mc.get(m.id).status == "running"

        # Complete with findings
        mc.complete(m.id,
                    result={"ok": True, "findings": [{"ETH": 0}]},
                    findings=[{"tool": "eth_check", "args": ["0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"]}],
                    tokens_in=500, tokens_out=200)

        m_final = mc.get(m.id)
        assert m_final.status == "done"
        assert m_final.tokens_in == 500
        assert len(m_final.findings) == 1
        assert m_final.findings[0]["tool"] == "eth_check"

        # Summary should reflect completion
        s = mc.summary()
        assert s["by_status"]["done"] == 1
        assert s["total_findings"] == 1
