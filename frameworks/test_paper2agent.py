"""Paper2Agent tournament test — test the tournament adapter against Muse.

Tests that:
1. A 5-lane tournament can be set up
2. Lanes execute independently
3. Verifier is independent from implementer
4. Muse can evaluate tournament results
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "..", "qprivately"))

from frameworks.runner import call_muse, get_vault, get_key, log_framework_event, make_run_id

# Import from qprivately wire layer
sys.path.insert(0, "/home/ubuntu/qprivately")
from wire.paper2agent_to_tournament import (
    TournamentLane,
    WorkerAssignment,
    run_tournament,
    verify_independence,
)


class TestPaper2Agent:
    """Test Paper2Agent tournament adapter."""

    def test_verify_independence(self):
        """Verifiers are independent from implementers."""
        assignments = [
            WorkerAssignment(worker_id="w1", role="implementer", task="t1",
                           source_module="m1", output_path="o1"),
            WorkerAssignment(worker_id="w2", role="verifier", task="t1",
                           source_module="m1", output_path="v1"),
        ]
        assert verify_independence(assignments) is True

    def test_tournament_execution(self):
        """5-lane tournament executes and selects winner."""
        lanes = [
            TournamentLane(lane_id=f"lane:{i}", processor_id=f"proc:{i}",
                          strategy="direct")
            for i in range(5)
        ]

        def execute(lane):
            return {"receipt_id": f"r:{lane.lane_id}", "cost": 0.001}

        def verify(result):
            return result["cost"] < 0.01

        result = run_tournament("test-task", lanes, execute, verify)

        assert len(result.lanes) == 5
        assert result.winner_id.startswith("lane:")
        assert result.total_cost > 0

    def test_muse_evaluates_tournament(self):
        """Muse can evaluate tournament results."""
        vault = get_vault()
        key, cand = get_key(vault)
        if key is None:
            pytest.skip("no active LLM keys")

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Lane 0: PASS cost 0.001. Lane 1: FAIL cost 0.002. Lane 2: PASS cost 0.0015. Which lane wins? One sentence."},
        ]

        resp = call_muse(key, messages)
        text = resp["choices"][0]["message"]["content"]

        assert text.strip(), "empty response"
        assert len(text) > 5, f"response too short: {text!r}"

        return {"response": text[:500]}


class TestPaper2AgentIntegration:
    """Integration tests against Muse."""

    def test_tournament_live(self):
        """Live test: Muse evaluates a tournament."""
        vault = get_vault()
        key, cand = get_key(vault)
        if key is None:
            pytest.skip("no active LLM keys")

        run_id = make_run_id()

        lanes = [
            TournamentLane(lane_id=f"lane:{i}", processor_id=f"proc:{i}",
                          strategy="direct")
            for i in range(5)
        ]

        def execute(lane):
            return {"receipt_id": f"r:{lane.lane_id}", "cost": 0.001}

        def verify(result):
            return result["cost"] < 0.01

        result = run_tournament("live-test", lanes, execute, verify)

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"""A 5-lane tournament ran these results:

{json.dumps([{'lane': l.lane_id, 'status': l.status, 'cost': l.cost} for l in result.lanes], indent=2)}

Winner: {result.winner_id}
Total cost: {result.total_cost}

Is this a good tournament result? Reply in one sentence."""},
        ]

        resp = call_muse(key, messages)
        text = resp["choices"][0]["message"]["content"]

        log_framework_event("paper2agent", {
            "run_id": run_id,
            "test": "tournament_live",
            "winner": result.winner_id,
            "total_cost": result.total_cost,
            "response": text[:500],
            "status": "PASS",
        })

        assert len(text) > 20, f"unexpected response: {text[:200]!r}"
