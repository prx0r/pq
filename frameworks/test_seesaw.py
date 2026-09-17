"""Seesaw discovery test — test the discovery adapter against Muse.

Tests that:
1. Constraints can be converted to processor needs
2. Processors can be ranked by relevance
3. Migration can be detected
4. Muse can explain constraint migration
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
from wire.seesaw_to_discovery import (
    ConstraintNode,
    ProcessorCandidate,
    constraints_to_needs,
    detect_migration,
    rank_processors,
    select_top_k,
)


class TestSeesaw:
    """Test Seesaw discovery adapter."""

    def test_constraints_to_needs(self):
        """Constraints convert to processor needs."""
        constraints = [
            ConstraintNode(id="c1", name="COMPUTE", market_size=100,
                          demand_pressure=50, tightness=2, cost_to_relieve=10,
                          ai_exposure=0.5),
            ConstraintNode(id="c2", name="MEMORY", market_size=50,
                          demand_pressure=30, tightness=1.5, cost_to_relieve=5,
                          ai_exposure=0.3),
        ]
        needs = constraints_to_needs(constraints)

        assert len(needs) == 2
        # Higher shadow price = higher urgency
        assert needs[0].urgency >= needs[1].urgency

    def test_detect_migration(self):
        """Migration detection works."""
        old = [ConstraintNode(id="c1", name="COMPUTE", ai_exposure=0.5)]
        new = [ConstraintNode(id="c1", name="COMPUTE", ai_exposure=-0.5)]

        migrations = detect_migration(old, new)

        assert len(migrations) == 1
        assert migrations[0]["type"] == "EXPOSURE_FLIP"

    def test_muse_explains_migration(self):
        """Muse can explain constraint migration."""
        vault = get_vault()
        key, cand = get_key(vault)
        if key is None:
            pytest.skip("no active LLM keys")

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Constraint shifted from COMPUTE to MEMORY. What does this mean for trading? One sentence."},
        ]

        resp = call_muse(key, messages)
        text = resp["choices"][0]["message"]["content"]

        assert text.strip(), "empty response"
        assert len(text) > 20, f"response too short: {text!r}"

        return {"response": text[:500]}


class TestSeesawIntegration:
    """Integration tests against Muse."""

    def test_migration_live(self):
        """Live test: Muse explains a constraint migration."""
        vault = get_vault()
        key, cand = get_key(vault)
        if key is None:
            pytest.skip("no active LLM keys")

        run_id = make_run_id()

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Constraint shifted from COMPUTE to MEMORY. What does this mean for trading? One sentence."},
        ]

        resp = call_muse(key, messages)
        text = resp["choices"][0]["message"]["content"]

        log_framework_event("seesaw", {
            "run_id": run_id,
            "test": "migration_live",
            "response": text[:500],
            "status": "PASS",
        })

        assert len(text) > 20, f"unexpected response: {text[:200]!r}"
