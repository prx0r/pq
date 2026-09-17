# TEST PLAN — full-scale testing for autonomous red-team system

## Philosophy

The system must prove it can find targets, extract secrets, and chain
receipts autonomously. Every test has a known answer. The agent must reach
it with a real LLM. No mocking — real model, real tools, real receipts.

## Scenario categories

### Level 1: Arena basics (synthetic, fast, key-free)
Prove the core loop works: probe → attempt → verify → receipt.

| ID | Target | Expected finding | Budget |
|---|---|---|---|
| L1-01 | weak-creds-01 | admin:admin → CAPTURED | 3 turns |
| L1-02 | traversal-01 | ../../flag.txt → CAPTURED | 3 turns |
| L1-03 | sqli-sim-01 | ' OR '1'='1 → CAPTURED | 3 turns |
| L1-04 | all 3 targets | 3/3 CAPTURED, chain verified | 9 turns |
| L1-05 | tournament | 3 lanes, winner ranked, gate passes | 1 run |

### Level 2: Real LLM through vault (key required)
Prove the vault → API → tracker → arena pipeline works end to end.

| ID | Scenario | Success condition |
|---|---|---|
| L2-01 | vault picks active key, calls mimo-v2.5, agent gets 1/3 | receipt + usage logged |
| L2-02 | full CTF run, all 3 targets captured | 3 receipts, chain verified, cost tracked |
| L2-03 | rate limit hit mid-run | circuit breaker trips, run continues with next key |
| L2-04 | key expires mid-run | graceful fallback, no crash |

### Level 3: Realistic CTF targets (synthetic repos with planted secrets)
Simulate finding secrets in repos: extract, classify, store, receipt.

| ID | Target | What's planted | Agent must find |
|---|---|---|---|
| L3-01 | planted-repo-1 | SECRET_KEY in .env committed then deleted | key in git history blob |
| L3-02 | planted-repo-2 | wallet address in README | extract address |
| L3-03 | planted-repo-3 | API key in config file | extract + classify |
| L3-04 | planted-repo-4 | passphrase in a reverted commit | find in git log |
| L3-05 | planted-repo-5 | signing key in source code | extract + verify |

### Level 4: Adversarial / edge cases
Prove the system doesn't break or leak.

| ID | Test | Expected |
|---|---|---|
| L4-01 | submit wrong flag | REJECTED, receipt still valid |
| L4-02 | use expired grant | "grant expired" error, no value leaked |
| L4-03 | try high-risk tool | denied, no execution |
| L4-04 | rate limit exhausted | backs off, doesn't crash |
| L4-05 | key rotation mid-run | old key stops working, new key works |

### Level 5: Full pipeline (integration)
Find a target, extract the secret, classify it, run tier scripts, store it.

| ID | Pipeline step | Tool chain |
|---|---|---|
| L5-01 | Find secret in repo | grep + git history scan |
| L5-02 | Extract private key | git cat-file on blob |
| L5-03 | Classify key type | classifier detects solana_key |
| L5-04 | Run tier scripts | check_sol_balance, derive_address |
| L5-05 | Store as vault asset | captured-sol-key-* with metadata |
| L5-06 | Full chain: find→extract→classify→scripts→store | all steps, one receipt |

## Planted test repos

Create 5 small repos with deterministic planted secrets:

```
planted/
├── repo-1/          # SECRET_KEY in .env committed then deleted
├── repo-2/          # wallet address in README
├── repo-3/          # API key in config file
├── repo-4/          # passphrase in reverted commit
└── repo-5/          # signing key in source code
```

Each repo is tiny (< 50 files), has exactly one secret type, and the
answer is deterministic. The agent must find it without being told where.

## Metrics

Every scenario records:
- turns: how many LLM turns to reach verdict
- time: wall-clock seconds
- tokens_in / tokens_out: from API response
- cost: calculated from vault pricing
- chain_ok: ledger hash chain verifies
- receipt_valid: receipt passes verification
- tools_used: which tools were called and how many times

## Pass criteria

- L1: 100% pass (synthetic, no LLM needed)
- L2: 100% pass with active key (vault → API → receipt)
- L3: 80%+ pass (realistic targets, some may need tuning)
- L4: 100% pass (security must never break)
- L5: proof of concept — at least one full pipeline completes

## What this proves

If the system passes L1–L5, it can:
1. Play CTF autonomously with a real LLM
2. Track its own usage and costs
3. Handle rate limits and key rotation
4. Find secrets in realistic targets
5. Chain receipts that verify
6. Never leak keys through any channel
7. Auto-classify found secrets and run tier-specific analysis
