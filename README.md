# pq — blueteamer live experiments

**By blueteamer. Testing qpbot with real LLM calls and on-chain tools.**

pq is where we prove our systems work against real APIs. Every test logs
to `runs/`. Every finding gets a QP receipt. Nothing is trusted —
everything is verified.

## What we experiment with

1. **Can mimo-v2.5 parse and execute tools correctly?** — Real API calls through the harness. Every response logged.

2. **Can our vault resolve keys under pressure?** — 5 keys, failover, rate limiting, usage tracking. Every resolution audited.

3. **Can our on-chain tools find real data?** — Whale feed, ETH balance, FOMO leaderboard. Real APIs, real results.

4. **Can QP proofs validate everything?** — Every finding gets a receipt. Every receipt is content-addressed and verifiable.

## Experiments

```bash
# Run all experiments
python3 frameworks/test_vault_real.py        # vault key resolution
python3 frameworks/test_arena_real.py        # arena tools (probe, creds, submit)
python3 frameworks/test_ledger_real.py       # ledger chain verification
python3 frameworks/test_qp_proof_reality.py  # QP proofs against real APIs
python3 frameworks/test_harness_real.py      # LLM harness (mimo-v2.5)
```

## Results

| Experiment | Tests | Result |
|------------|-------|--------|
| Vault key resolution | 4 | ✓ All pass |
| Arena tools | 8 | ✓ All pass |
| Ledger chain verification | 7 | ✓ All pass |
| QP proofs against real APIs | 4 | ✓ All pass |
| LLM harness (mimo-v2.5) | 5 | ✓ 4 pass, 1 skip |

## QP proofs against real data

```python
# Whale feed → QP proof
whale_feed(10000) → 7 transactions → evidence → gates → receipt

# ETH balance → QP proof
eth_check(0xd8dA...) → balance data → evidence → gates → receipt

# FOMO leaderboard → QP proof
fomo_leaderboard("leaderboard") → trader data → evidence → gates → receipt
```

Every receipt is content-addressed. Anyone can verify.

## What we proved

| Experiment | QP Proof | Receipt |
|------------|----------|---------|
| Whale transactions exist | PASS | receipt:9d76b878... |
| ETH balance API works | PASS | receipt:2b554f97... |
| FOMO leaderboard returns data | PASS | receipt:9b7ff69b... |
| Muse explains whale activity | PASS | (live response logged) |

## Layout

```
pq/
  core/           Arena game engine (copied from qpbot)
  agentcom/       Control plane: vault, authority, htasks
  harness.py      Live LLM test runner
  frameworks/     Experiment scripts + QP proofs
  scripts/        Automation (ask, live, smoke)
  scanners/       On-chain tools
  tests/          Unit tests
  specs/          Canonical spec tree
  runs/           Experiment logs (gitignored)
```

## Rules

1. Every experiment logs to `runs/`. No silent runs.
2. Every finding gets a QP receipt. No unverified claims.
3. Keys stay in vault. Never in code or logs.
4. Code flows qpbot → pq. pq never edits qpbot.
5. We test our own systems. Nothing is trusted — everything is proven.
