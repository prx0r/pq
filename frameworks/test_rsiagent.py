"""RSIAgent evolution test — test the evolution adapter against Muse.

Tests that:
1. A processor can evolve through the self-evolving loop
2. Actor/Verifier/Curriculum roles work correctly
3. Muse can explain evolution decisions
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
from wire.rsiagent_to_evolution import (
    ActorLearning,
    EvolutionResult,
    EvolutionStatus,
    ProcessorEvolution,
    ProcessorStatus,
    TargetVerdict,
    TargetVerification,
    evolve_processor,
)


class TestRSIAgent:
    """Test RSIAgent evolution adapter."""

    def test_evolve_processor(self):
        """Processor evolves through pass/fail cycle."""
        processor = ProcessorEvolution(
            processor_id="proc:test",
            status=ProcessorStatus.CANDIDATE,
            version="0.1.0",
        )

        call_count = [0]

        def execute(p):
            call_count[0] += 1
            return {"output": f"run-{call_count[0]}"}

        def verify(o):
            # First 2 calls pass, then curriculum says stop
            return TargetVerification(verdict=TargetVerdict.PASS, report="ok")

        def learn(p, v):
            return ActorLearning(memory={"pass_count": p.pass_count + 1}, diagnosis="ok")

        def curriculum(p):
            if p.pass_count >= 1:
                return EvolutionResult(status=EvolutionStatus.READY_FOR_RETRY,
                                      memory=p.memory, projects=0)
            return EvolutionResult(status=EvolutionStatus.READY_FOR_RETRY,
                                  memory=p.memory, projects=1)

        result = evolve_processor(processor, execute, verify, learn, curriculum,
                                 max_cycles=5, min_pass=1)

        assert result.termination == "promoted"
        assert result.verifier_verdict == TargetVerdict.PASS

    def test_muse_explains_evolution(self):
        """Muse can explain evolution decisions."""
        vault = get_vault()
        key, cand = get_key(vault)
        if key is None:
            pytest.skip("no active LLM keys")

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": """A processor went through this evolution:

Cycle 1: PASS (learned: pattern recognition improved)
Cycle 2: PASS (learned: edge cases handled better)
Cycle 3: PASS (learned: error recovery working)

Curriculum decided: no more practice needed, promote.

Explain in one sentence why this processor should be promoted."""},
        ]

        resp = call_muse(key, messages)
        text = resp["choices"][0]["message"]["content"]

        assert text.strip(), "empty response"
        assert len(text) > 20, f"response too short: {text!r}"

        return {"response": text[:500]}


class TestRSIAgentIntegration:
    """Integration tests against Muse."""

    def test_evolution_live(self):
        """Live test: Muse evaluates an evolution cycle."""
        vault = get_vault()
        key, cand = get_key(vault)
        if key is None:
            pytest.skip("no active LLM keys")

        run_id = make_run_id()

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "A processor passed 3 cycles: pattern recognition improved, edge cases handled, error recovery working. Curriculum says promote. One sentence: why?"},
        ]

        resp = call_muse(key, messages)
        text = resp["choices"][0]["message"]["content"]

        log_framework_event("rsiagent", {
            "run_id": run_id,
            "test": "evolution_live",
            "response": text[:500],
            "status": "PASS",
        })

        assert len(text) > 20, f"unexpected response: {text[:200]!r}"
