"""RSI tests — investigation logging, analysis, optimization feedback.

Tests the full learning loop: log investigation steps → analyze patterns
→ feed insights back to memory bank → next run uses learned knowledge.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from agentcom.invlog import InvestigationLog
from agentcom.rsi import analyze, format_insights


# ── Investigation logging ──────────────────────────────────────────────

def test_invlog_start():
    with tempfile.TemporaryDirectory() as d:
        log = InvestigationLog(os.path.join(d, "inv.jsonl"))
        run_id = log.log_start("0xabc", "find_funded_wallet")
        assert run_id.startswith("inv-")

def test_invlog_step():
    with tempfile.TemporaryDirectory() as d:
        log = InvestigationLog(os.path.join(d, "inv.jsonl"))
        rid = log.log_start("0xabc")
        log.log_step(rid, "eth_check", ["0xabc"],
                     {"ETH": 100, "total_usd": 250000}, duration_ms=1500)
        # Verify file has 2 entries
        with open(os.path.join(d, "inv.jsonl")) as f:
            lines = [l.strip() for l in f if l.strip()]
        assert len(lines) == 2
        step = json.loads(lines[1])
        assert step["tool"] == "eth_check"
        assert step["signals_found"] >= 1

def test_invlog_prize():
    with tempfile.TemporaryDirectory() as d:
        log = InvestigationLog(os.path.join(d, "inv.jsonl"))
        rid = log.log_start("0xabc")
        log.log_prize(rid, {"chain": "ethereum", "key_type": "eth_key",
                            "balance_usd": 250000, "github_repos": ["user/repo"],
                            "ens_name": "vitalik.eth", "confidence": "high"})
        with open(os.path.join(d, "inv.jsonl")) as f:
            lines = [l.strip() for l in f if l.strip()]
        prize = json.loads(lines[-1])
        assert prize["event"] == "prize"
        assert prize["has_github"] is True
        assert prize["has_ens"] is True

def test_invlog_end():
    with tempfile.TemporaryDirectory() as d:
        log = InvestigationLog(os.path.join(d, "inv.jsonl"))
        rid = log.log_start("0xabc")
        log.log_end(rid, "completed", total_steps=3, total_signals=5, prize_stored=True)
        with open(os.path.join(d, "inv.jsonl")) as f:
            lines = [l.strip() for l in f if l.strip()]
        end = json.loads(lines[-1])
        assert end["event"] == "end"
        assert end["total_steps"] == 3
        assert end["prize_stored"] is True

def test_invlog_iter_runs():
    with tempfile.TemporaryDirectory() as d:
        log = InvestigationLog(os.path.join(d, "inv.jsonl"))
        rid1 = log.log_start("0xabc")
        log.log_step(rid1, "eth_check", ["0xabc"], {"ETH": 100})
        log.log_end(rid1, "completed", 2, 3, True)
        rid2 = log.log_start("0xdef")
        log.log_step(rid2, "sol_check", ["0xdef"], {"SOL": 50})
        log.log_end(rid2, "completed", 1, 1, False)
        runs = list(log.iter_runs())
        assert len(runs) == 2

def test_invlog_full_investigation():
    """Simulate a full investigation log."""
    with tempfile.TemporaryDirectory() as d:
        log = InvestigationLog(os.path.join(d, "inv.jsonl"))
        rid = log.log_start("0x28c6c06298d514db089934071355e5743bf21d60",
                           "find_github_for_wallet")
        # Step 1: whale feed
        log.log_step(rid, "whale_feed", ["100000"],
                     {"txs": [{"from": ["0x28c6c062..."]}], "count": 5})
        # Step 2: balance check
        log.log_step(rid, "eth_check", ["0x28c6c062..."],
                     {"ETH": 600, "total_usd": 1500000})
        # Step 3: investigate
        log.log_step(rid, "wallet_investigate", ["0x28c6c062..."],
                     {"signals": ["ENS: binance.eth", "GitHub: found in 2 repos"],
                      "handles": [{"handle": "binance", "source": "ens", "confidence": "high"}],
                      "github_repos": [{"repo": "binance/ethereum"}],
                      "confidence": "high"})
        # Step 4: classify
        log.log_step(rid, "drain_classify", ["0x28c6c062..."],
                     {"kind": "eth_key", "authority": "root_signer"})
        # Prize
        log.log_prize(rid, {"chain": "ethereum", "key_type": "eth_key",
                            "balance_usd": 1500000, "github_repos": ["binance/ethereum"],
                            "ens_name": "binance.eth", "confidence": "high"})
        log.log_end(rid, "completed", 4, 5, True)

        runs = list(log.iter_runs())
        assert len(runs) == 1
        rid, run = runs[0]
        assert len(run["steps"]) == 4
        assert run["prize"]["has_github"] is True


# ── RSI analysis ───────────────────────────────────────────────────────

def test_rsi_no_data():
    with tempfile.TemporaryDirectory() as d:
        insights = analyze(os.path.join(d, "nonexistent.jsonl"))
        assert insights["status"] == "no_data"

def test_rsi_empty_log():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "inv.jsonl")
        open(path, "w").close()
        insights = analyze(path)
        assert insights["total_runs"] == 0

def test_rsi_analyze_basic():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "inv.jsonl")
        log = InvestigationLog(path)
        # Run 1: successful
        rid1 = log.log_start("0xabc", "find_funded")
        log.log_step(rid1, "whale_feed", [], {"txs": [{"from": ["0x1"]}], "count": 5})
        log.log_step(rid1, "wallet_investigate", ["0x1"],
                     {"signals": ["ENS: vitalik.eth"], "handles": [{"handle": "vitalik"}]})
        log.log_prize(rid1, {"chain": "ethereum", "has_github": True, "has_ens": True})
        log.log_end(rid1, "completed", 2, 3, True)
        # Run 2: no prize
        rid2 = log.log_start("0xdef", "find_funded")
        log.log_step(rid2, "whale_feed", [], {"txs": [], "count": 0})
        log.log_end(rid2, "completed", 1, 1, False)

        insights = analyze(path)
        assert insights["total_runs"] == 2
        assert insights["runs_with_prize"] == 1
        assert insights["prize_rate"] == 0.5

def test_rsi_signal_ranking():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "inv.jsonl")
        log = InvestigationLog(path)
        rid = log.log_start("0xabc")
        log.log_step(rid, "wallet_investigate", ["0x1"],
                     {"signals": ["ENS: vitalik.eth", "Farcaster: @vitalik",
                                  "GitHub: found in 2 repos"],
                      "handles": []})
        log.log_end(rid, "completed", 1, 3, False)
        insights = analyze(path)
        assert len(insights["signal_ranking"]) >= 1

def test_rsi_tool_ranking():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "inv.jsonl")
        log = InvestigationLog(path)
        rid = log.log_start("0xabc")
        log.log_step(rid, "eth_check", [], {"ETH": 100, "total_usd": 250000})
        log.log_step(rid, "eth_check", [], {"ETH": 50, "total_usd": 125000})
        log.log_step(rid, "sol_check", [], {"SOL": 200})
        log.log_end(rid, "completed", 3, 2, False)
        insights = analyze(path)
        assert len(insights["tool_ranking"]) >= 2

def test_rsi_suggestions():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "inv.jsonl")
        log = InvestigationLog(path)
        # Only 1 run with 1 step
        rid = log.log_start("0xabc")
        log.log_step(rid, "eth_check", [], {"ETH": 100})
        log.log_end(rid, "completed", 1, 1, False)
        insights = analyze(path)
        # Should suggest improvements
        assert len(insights["suggestions"]) > 0

def test_rsi_format_insights():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "inv.jsonl")
        log = InvestigationLog(path)
        rid = log.log_start("0xabc")
        log.log_step(rid, "wallet_investigate", ["0x1"],
                     {"signals": ["ENS: vitalik.eth"], "handles": [{"handle": "vitalik"}]})
        log.log_prize(rid, {"chain": "ethereum", "has_github": True, "has_ens": True})
        log.log_end(rid, "completed", 1, 2, True)
        insights = analyze(path)
        text = format_insights(insights)
        assert "RSI Analysis" in text
        assert "Prize rate" in text

def test_rsi_prize_stats():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "inv.jsonl")
        log = InvestigationLog(path)
        rid = log.log_start("0xabc")
        log.log_prize(rid, {"chain": "ethereum", "github_repos": ["user/repo"],
                            "ens_name": "vitalik.eth"})
        log.log_prize(rid, {"chain": "solana"})
        log.log_end(rid, "completed", 0, 0, True)
        insights = analyze(path)
        ps = insights["prize_stats"]
        assert ps["total"] == 2
        assert ps["with_github"] == 1
        assert ps["with_ens"] == 1
        assert ps["by_chain"]["ethereum"] == 1
        assert ps["by_chain"]["solana"] == 1


# ── Integration with memory bank ───────────────────────────────────────

def test_rsi_feeds_memory_bank():
    """RSI insights should be formatable for the memory bank."""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "inv.jsonl")
        log = InvestigationLog(path)
        rid = log.log_start("0xabc")
        log.log_step(rid, "wallet_investigate", ["0x1"],
                     {"signals": ["ENS: vitalik.eth", "Farcaster: @vitalik"],
                      "handles": [{"handle": "vitalik"}],
                      "confidence": "high"})
        log.log_prize(rid, {"chain": "ethereum", "has_github": True, "has_ens": True,
                            "confidence": "high"})
        log.log_end(rid, "completed", 1, 3, True)

        insights = analyze(path)
        text = format_insights(insights)

        # Should be usable as memory bank content
        assert len(text) > 50
        assert "ENS" in text or "signals" in text.lower()
