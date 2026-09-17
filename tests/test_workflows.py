"""Workflow and prize tests — decompose goals, validate, store prizes.

Tests the full chain: workflow decomposition -> tool execution ->
QP validation -> prize storage with full context.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from agentcom.workflows import (
    WORKFLOWS, WorkflowRunner, WorkflowResult, Step, StepResult,
    extract_wallet_info, define_workflow,
)
from agentcom.prizes import PrizeStore
from scanners.registry import fire


# ── Workflow definitions ───────────────────────────────────────────────

def test_workflows_defined():
    assert "find_funded_wallet" in WORKFLOWS
    assert "find_github_for_wallet" in WORKFLOWS
    assert "capture_prize" in WORKFLOWS
    assert "scan_repo_secrets" in WORKFLOWS

def test_workflow_has_steps():
    wf = WORKFLOWS["find_funded_wallet"]
    assert len(wf["steps"]) >= 2
    assert wf["steps"][0].tool == "whale_feed"

def test_workflow_step_args_building():
    step = Step(name="check", tool="eth_check",
                args_from={"0": "$whale.txs.0.from.0"})
    context = {"whale": {"txs": [{"from": ["0xabc123"]}]}}
    args = step.build_args(context)
    assert args == ["0xabc123"]

def test_workflow_step_constant_args():
    step = Step(name="feed", tool="whale_feed", args_from={"0": "500000"})
    args = step.build_args({})
    assert args == ["500000"]

def test_workflow_step_validation_pass():
    step = Step(name="check", tool="eth_check", validate="total_usd > 0")
    output = {"total_usd": 1500.0}
    valid, evidence = step.validate_output(output)
    assert valid is True

def test_workflow_step_validation_fail():
    step = Step(name="check", tool="eth_check", validate="total_usd > 1000")
    output = {"total_usd": 500.0}
    valid, evidence = step.validate_output(output)
    assert valid is False
    assert "500" in evidence

def test_workflow_step_no_validation():
    step = Step(name="scan", tool="clone_scan")
    valid, evidence = step.validate_output({"anything": True})
    assert valid is True
    assert "no validation" in evidence


# ── Workflow runner ────────────────────────────────────────────────────

def test_runner_unknown_workflow():
    def fake_exec(tool, args): return {"ok": True}
    runner = WorkflowRunner(fake_exec)
    result = runner.run("nonexistent")
    assert result.status == "failed"

def test_runner_executes_steps():
    calls = []
    def fake_exec(tool, args):
        calls.append((tool, args))
        if tool == "whale_feed":
            return {"ok": True, "data": {"count": 2, "txs": [{"from": ["0xabc"], "usd_approx": 500000}]}}
        elif tool == "eth_check":
            return {"ok": True, "data": {"ETH": 100, "total_usd": 250000}}
        elif tool == "drain_classify":
            return {"ok": True, "data": {"kind": "eth_key", "authority": "root_signer"}}
        return {"ok": True, "data": {}}

    runner = WorkflowRunner(fake_exec)
    result = runner.run("find_funded_wallet")
    assert result.status in ("completed", "completed_with_warnings")
    assert len(result.steps) >= 2
    assert calls[0][0] == "whale_feed"

def test_runner_passes_context_between_steps():
    def fake_exec(tool, args):
        if tool == "whale_feed":
            return {"txs": [{"from": ["0xabc123"], "chain": "ethereum"}]}
        elif tool == "eth_check":
            # Should receive the address from previous step
            assert args[0] == "0xabc123", f"Expected 0xabc123, got {args}"
            return {"ETH": 10, "total_usd": 25000}
        return {}

    runner = WorkflowRunner(fake_exec)
    result = runner.run("find_funded_wallet")
    assert len(result.steps) >= 2

def test_runner_stores_outputs_in_context():
    def fake_exec(tool, args):
        if tool == "whale_feed":
            return {"txs": [{"from": ["0xaddr"], "usd_approx": 1000000}]}
        elif tool == "eth_check":
            return {"total_usd": 2500000}
        elif tool == "drain_classify":
            return {"kind": "eth_key"}
        return {}

    runner = WorkflowRunner(fake_exec)
    result = runner.run("find_funded_wallet")
    # Each step's output should be accessible
    assert result.steps[0].output.get("txs") is not None


# ── Prize storage ──────────────────────────────────────────────────────

def test_prize_store():
    with tempfile.TemporaryDirectory() as d:
        ps = PrizeStore(os.path.join(d, "prizes.jsonl"))
        prize = ps.store(
            wallet_address="0xabc123",
            chain="ethereum",
            wallet_kind="evm",
            key_type="eth_key",
            drain_class="root_signer",
            balance_usd=25000,
            github_repos=["user/repo"],
            fomo_handle="trader1",
        )
        assert prize["wallet_address"] == "0xabc123"
        assert prize["chain"] == "ethereum"
        assert prize["hash"]
        assert prize["prev"] == "genesis"

def test_prize_hash_chain():
    with tempfile.TemporaryDirectory() as d:
        ps = PrizeStore(os.path.join(d, "prizes.jsonl"))
        ps.store(wallet_address="0x1", chain="ethereum", wallet_kind="evm")
        ps.store(wallet_address="0x2", chain="solana", wallet_kind="solana")
        ps.store(wallet_address="0x3", chain="bitcoin", wallet_kind="btc")
        assert ps.verify_chain()

def test_prize_tamper_detection():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "prizes.jsonl")
        ps = PrizeStore(path)
        ps.store(wallet_address="0x1", chain="ethereum", wallet_kind="evm")
        ps.store(wallet_address="0x2", chain="solana", wallet_kind="solana")
        # Tamper with first prize
        with open(path) as f:
            lines = f.readlines()
        prize = json.loads(lines[0])
        prize["balance_usd"] = 999999
        lines[0] = json.dumps(prize) + "\n"
        with open(path, "w") as f:
            f.writelines(lines)
        ps2 = PrizeStore(path)
        assert not ps2.verify_chain()

def test_prize_list_filter():
    with tempfile.TemporaryDirectory() as d:
        ps = PrizeStore(os.path.join(d, "prizes.jsonl"))
        ps.store(wallet_address="0x1", chain="ethereum", wallet_kind="evm", balance_usd=50000)
        ps.store(wallet_address="0x2", chain="solana", wallet_kind="solana", balance_usd=500)
        ps.store(wallet_address="0x3", chain="ethereum", wallet_kind="evm", balance_usd=100000)
        eth = ps.list_prizes(chain="ethereum")
        assert len(eth) == 2
        rich = ps.list_prizes(min_usd=10000)
        assert len(rich) == 2

def test_prize_summary():
    with tempfile.TemporaryDirectory() as d:
        ps = PrizeStore(os.path.join(d, "prizes.jsonl"))
        ps.store(wallet_address="0x1", chain="ethereum", wallet_kind="evm",
                 key_type="eth_key", drain_class="root_signer", balance_usd=50000)
        ps.store(wallet_address="0x2", chain="solana", wallet_kind="solana",
                 key_type="solana_key", drain_class="root_signer", balance_usd=500)
        s = ps.summary()
        assert s["total"] == 2
        assert s["by_chain"]["ethereum"] == 1
        assert s["by_chain"]["solana"] == 1
        assert s["total_usd"] == 50500

def test_prize_persistence():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "prizes.jsonl")
        ps1 = PrizeStore(path)
        ps1.store(wallet_address="0xabc", chain="ethereum", wallet_kind="evm")
        ps2 = PrizeStore(path)
        assert len(ps2.prizes) == 1
        assert ps2.prizes[0]["wallet_address"] == "0xabc"

def test_prize_full_context():
    with tempfile.TemporaryDirectory() as d:
        ps = PrizeStore(os.path.join(d, "prizes.jsonl"))
        prize = ps.store(
            wallet_address="0x28c6c06298d514db089934071355e5743bf21d60",
            chain="ethereum",
            wallet_kind="evm",
            key_type="eth_key",
            drain_class="root_signer",
            balance_usd=1500000,
            balance_proof={"ETH": 600, "total_usd": 1500000},
            github_repos=["binance/ethereum", "binance/exchange"],
            github_handles=["binance"],
            fomo_handle="",
            signals=["FOMO trader: binance", "Found in 2 GitHub repos"],
            found_secret="0xabc123def456...",
            found_name="binance-cold-wallet",
            tool="eth_check",
            evidence="Binance hot wallet, 600 ETH",
            workflow="capture_prize",
            mission_id="m-12345",
        )
        assert prize["chain"] == "ethereum"
        assert len(prize["github_repos"]) == 2
        assert len(prize["signals"]) == 2
        assert prize["workflow"] == "capture_prize"


# ── Extract wallet info from workflow ──────────────────────────────────

def test_extract_wallet_info():
    steps = [
        StepResult(step="find_wallet", tool="whale_feed",
                   args=[], output={"txs": [{"from": ["0xabc"], "chain": "ethereum"}]}),
        StepResult(step="verify_funded", tool="eth_check",
                   args=[], output={"ETH": 100, "total_usd": 250000}),
        StepResult(step="classify_key", tool="drain_classify",
                   args=[], output={"kind": "eth_key", "authority": "root_signer"}),
    ]
    result = WorkflowResult(workflow="capture_prize", goal="test",
                            steps=steps, status="completed")
    info = extract_wallet_info(result)
    assert info["chain"] == "ethereum"
    assert info["wallet_kind"] == "evm"
    assert info["balance_usd"] == 250000
    assert info["key_type"] == "eth_key"
    assert info["drain_class"] == "root_signer"

def test_extract_wallet_info_solana():
    steps = [
        StepResult(step="find_wallet", tool="whale_feed",
                   args=[], output={"txs": [{"from": ["0xaddr"], "chain": "solana"}]}),
        StepResult(step="check_balance", tool="sol_check",
                   args=[], output={"SOL": 500, "sol_usd": 75000}),
    ]
    result = WorkflowResult(workflow="test", goal="test",
                            steps=steps, status="completed")
    info = extract_wallet_info(result)
    assert info["chain"] == "solana"
    assert info["wallet_kind"] == "solana"
    assert info["balance_usd"] == 75000


# ── Live workflow with real tools ──────────────────────────────────────

def test_live_find_funded_wallet():
    """Run the find_funded_wallet workflow with real tools. Spends network."""
    runner = WorkflowRunner(fire)
    result = runner.run("find_funded_wallet")
    assert result.status in ("completed", "completed_with_warnings")
    assert len(result.steps) >= 2
    # Check that whale_feed produced results
    whale_step = result.steps[0]
    assert whale_step.output.get("ok") is True or whale_step.output.get("count", 0) > 0


# ── Custom workflow definition ─────────────────────────────────────────

def test_custom_workflow():
    define_workflow(
        name="test_custom",
        goal="test custom workflow",
        steps=[
            Step(name="s1", tool="whale_feed", args_from={"0": "1000000"}),
            Step(name="s2", tool="eth_check",
                 args_from={"0": "$s1.txs.0.from.0"}),
        ],
    )
    assert "test_custom" in WORKFLOWS
    assert len(WORKFLOWS["test_custom"]["steps"]) == 2
