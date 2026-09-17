"""On-chain tools tests — balance checkers, whale feed, FOMO, clone+scan.

Tests the new on-chain discovery tools that enable the
"find wallet → GitHub cross-reference" game mechanic.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scanners.registry import fire, tool_names, TOOLS


# ── Registry wiring ────────────────────────────────────────────────────

def test_all_new_tools_registered():
    expected = {"whale_feed", "fomo_leaderboard", "wallet_github",
                "clone_scan", "eth_check", "sol_check",
                "gh_search", "env_scan", "git_history",
                "classify", "drain_classify", "batch_check",
                "mnemonic_derive"}
    assert expected.issubset(set(tool_names()))

def test_whale_feed_tool_exists():
    assert "whale_feed" in TOOLS
    assert TOOLS["whale_feed"].needs_net is True

def test_fomo_leaderboard_tool_exists():
    assert "fomo_leaderboard" in TOOLS
    assert TOOLS["fomo_leaderboard"].needs_net is True

def test_wallet_github_tool_exists():
    assert "wallet_github" in TOOLS
    assert TOOLS["wallet_github"].needs_net is True

def test_clone_scan_tool_exists():
    assert "clone_scan" in TOOLS
    assert TOOLS["clone_scan"].needs_net is True


# ── ETH balance checker (free RPC, no key) ─────────────────────────────

def test_eth_check_known_address():
    """Check Binance hot wallet — should return valid data structure."""
    result = fire("eth_check", ["0x28c6c06298d514db089934071355e5743bf21d60"])
    assert result["ok"] is True
    data = result["data"]
    assert "ETH" in data
    assert "total_usd" in data
    assert isinstance(data["ETH"], (int, float))

def test_eth_check_empty_address():
    """Check an empty address — should return 0."""
    result = fire("eth_check", ["0x0000000000000000000000000000000000000000"])
    assert result["ok"] is True
    assert result["data"]["ETH"] == 0

def test_eth_check_returns_erc20():
    result = fire("eth_check", ["0x28c6c06298d514db089934071355e5743bf21d60"])
    assert result["ok"] is True
    assert "USDC" in result["data"]
    assert "USDT" in result["data"]
    assert "DAI" in result["data"]


# ── SOL balance checker (free RPC, no key) ─────────────────────────────

def test_sol_check_known_address():
    """Check a known Solana address."""
    result = fire("sol_check", ["11111111111111111111111111111111"])
    assert result["ok"] is True
    data = result["data"]
    assert "SOL" in data
    assert "spl_count" in data


# ── Whale feed (no key) ────────────────────────────────────────────────

def test_whale_feed_returns_transactions():
    result = fire("whale_feed", [])
    assert result["ok"] is True
    data = result["data"]
    assert "txs" in data
    assert "count" in data
    assert "sources" in data

def test_whale_feed_min_usd_filter():
    result = fire("whale_feed", ["1000000"])
    assert result["ok"] is True
    # All returned txs should be above the filter
    for tx in result["data"].get("txs", []):
        assert tx.get("usd_approx", 0) >= 1000000

def test_whale_feed_tx_shape():
    result = fire("whale_feed", [])
    assert result["ok"] is True
    for tx in result["data"].get("txs", [])[:3]:
        assert "chain" in tx
        assert "tx_hash" in tx
        assert "amount" in tx
        assert "symbol" in tx
        assert "usd_approx" in tx


# ── FOMO leaderboard (no key) ─────────────────────────────────────────

def test_fomo_leaderboard():
    result = fire("fomo_leaderboard", ["leaderboard"])
    # May fail if fomo.family blocks scraping, but tool should handle gracefully
    assert result["ok"] is True
    assert "data" in result

def test_fomo_lookup():
    result = fire("fomo_leaderboard", ["lookup", "cupsey"])
    # May fail if API is down, but should not crash
    assert "tool" in result
    assert result["tool"] == "fomo_leaderboard"


# ── Wallet GitHub search (needs GH_TOKEN) ──────────────────────────────

def test_wallet_github_no_token_skip():
    """Without GH_TOKEN, search should return rate-limited or empty."""
    if not os.environ.get("GH_TOKEN"):
        pytest.skip("GH_TOKEN not set")
    result = fire("wallet_github", ["address", "0x0000000000000000000000000000000000000000"])
    assert "tool" in result
    assert result["tool"] == "wallet_github"


# ── Clone and scan ─────────────────────────────────────────────────────

def test_clone_scan_local_dir():
    """Scan a local directory (the pq repo itself)."""
    result = fire("clone_scan", [os.path.join(ROOT, "scanners")])
    assert result["ok"] is True
    data = result["data"]
    assert "scan" in data
    assert "summary" in data
    assert data["local"] is True

def test_clone_scan_returns_findings_shape():
    result = fire("clone_scan", [os.path.join(ROOT, "scripts", "simulations")])
    assert result["ok"] is True
    data = result["data"]
    assert "git_history" in data["scan"]
    assert "env_files" in data["scan"]
    assert "total_secrets" in data

def test_clone_scan_nonexistent_local():
    result = fire("clone_scan", ["/nonexistent/path"])
    assert result["ok"] is True
    data = result["data"]
    # Should handle gracefully, not crash
    assert "error" in data or "scan" in data


# ── Classifier integration ─────────────────────────────────────────────

def test_classify_eth_key():
    key = "0x4c0883a69102937d6231471b5dbb6204fe51296170827936ea5cce4b76f1d4f4"
    result = fire("classify", [key])
    assert result["ok"] is True
    data = result["data"]
    kind = data.get("kind", data.get("type", ""))
    assert kind in ("eth_key", "generic_secret", "unknown")

def test_classify_sol_key():
    key = "66URqAQFPLzVBMnGxqYqEybTcKDqWvNkUMjBEjRMHmLgJYrVQBWHfpATnJKcS3QwSHJGpCBvBzQvJxBqYHkF3mj"
    result = fire("classify", [key])
    assert result["ok"] is True

def test_classify_mnemonic():
    mnemonic = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
    result = fire("classify", [mnemonic])
    assert result["ok"] is True
    data = result["data"]
    assert "mnemonic" in str(data.get("type", "")).lower() or "mnemonic" in str(data).lower()


# ── Drain classify ─────────────────────────────────────────────────────

def test_drain_classify_eth_key():
    key = "0x4c0883a69102937d6231471b5dbb6204fe51296170827936ea5cce4b76f1d4f4"
    result = fire("drain_classify", [key])
    assert result["ok"] is True
    data = result["data"]
    assert "authority" in str(data).lower() or "class" in str(data).lower()

def test_drain_classify_mnemonic():
    mnemonic = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
    result = fire("drain_classify", [mnemonic, "24"])
    assert result["ok"] is True


# ── Wallet identity resolution ─────────────────────────────────────────

def test_wallet_identity_registered():
    assert "wallet_identity" in TOOLS
    assert TOOLS["wallet_identity"].needs_net is True

def test_wallet_identity_returns_structure():
    """Identity resolution for any address should return structured output."""
    result = fire("wallet_identity", ["0x0000000000000000000000000000000000000000"])
    assert result["ok"] is True
    data = result["data"]
    assert "address" in data
    assert "signals" in data
    assert "handles" in data
    assert "github_repos" in data
    assert "summary" in data

def test_wallet_identity_fomo_resolution():
    """Try to resolve a known FOMO trader's wallet."""
    # This may not find anything for a random address, but should not crash
    result = fire("wallet_identity", ["0x28c6c06298d514db089934071355e5743bf21d60"])
    assert result["ok"] is True
    assert isinstance(result["data"]["signals"], list)

def test_wallet_identity_github_search():
    """GitHub address search should return results for any address."""
    result = fire("wallet_identity", ["0xdead000000000000000000000000000000000000"])
    assert result["ok"] is True
    data = result["data"]
    assert "github_repos" in data
    assert "social_profiles" in data


# ── Shared patterns module ─────────────────────────────────────────────

def test_patterns_import():
    from scanners.patterns import SCAN_PATTERNS, DRAIN_PATTERNS, redact, extract_from_text
    assert len(SCAN_PATTERNS) > 10
    assert len(DRAIN_PATTERNS) >= 4

def test_redact():
    from scanners.patterns import redact
    assert redact("0x1234567890abcdef") == "0x123456...cdef"
    assert redact("short") == "short"

def test_extract_from_text():
    from scanners.patterns import extract_from_text
    text = 'PRIVATE_KEY=0x4c0883a69102937d6231471b5dbb6204fe51296170827936ea5cce4b76f1d4f4\nAWS_SECRET=AKIAIOSFODNN7EXAMPLE'
    found = extract_from_text(text)
    assert len(found) >= 2
    types = {f["type"] for f in found}
    assert "eth_private_key" in types or "aws_access_key" in types


# ── Shared RPC module ──────────────────────────────────────────────────

def test_rpc_import():
    from scripts.simulations.rpc import eth_balance, sol_balance, eth_rpc, sol_rpc
    assert callable(eth_balance)
    assert callable(sol_balance)


# ── Wallet investigation (full OSINT chain) ────────────────────────────

def test_wallet_investigate_registered():
    assert "wallet_investigate" in TOOLS
    assert TOOLS["wallet_investigate"].needs_net is True

def test_wallet_investigate_returns_full_structure():
    result = fire("wallet_investigate", ["0x0000000000000000000000000000000000000000"])
    assert result["ok"] is True
    data = result["data"]
    assert "address" in data
    assert "signals" in data
    assert "handles" in data
    assert "github_repos" in data
    assert "social_profiles" in data
    assert "confidence" in data
    assert "summary" in data

def test_wallet_investigate_confidence_scoring():
    result = fire("wallet_investigate", ["0x0000000000000000000000000000000000000000"])
    assert result["ok"] is True
    assert result["data"]["confidence"] in ("low", "medium", "high")

def test_wallet_investigate_phases():
    result = fire("wallet_investigate", ["0x28c6c06298d514db089934071355e5743bf21d60"])
    assert result["ok"] is True
    data = result["data"]
    assert isinstance(data["signals"], list)
    assert isinstance(data["handles"], list)
    assert data["summary"]["signals_count"] == len(data["signals"])
