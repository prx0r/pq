# pq — testing suite for qpbot

pq is the **live testing suite** for [qpbot](/home/ubuntu/qpbot). It runs a
real LLM (Muse on OpenCode Go) against qpbot's simulated CTF arena and
logs every result. The passing criteria is not just green tests -- it's
that every run leaves a trace in `runs/`.

qpbot owns the game engine, vault, tournament, autopilot, and 56 unit
tests (no external dependencies). pq pulls from qpbot and adds the one
thing qpbot doesn't have: **real LLM calls against the arena**.

## What pq tests

pq exercises qpbot end-to-end:

1. **Arena correctness** -- 3 targets (weak creds, path traversal, SQL
   injection) with server-side flag verification. Every claim settles
   through `arena.submit_flag()`.
2. **Live LLM harness** -- real model (Muse) parses tool calls, executes
   them via `core.cli` subprocess, feeds results back. Multi-turn loop
   with spend caps.
3. **Vault integration** -- encrypted key storage, scoped grants, usage
   tracking. Keys resolve, failover, and exhaust correctly.
4. **Authority grants** -- Ed25519-signed grants with atomic use-counter
   consumption. Tamper detection, expiry, revocation.
5. **Deterministic scanners** -- banner, creds, traversal, SQLi. No LLM
   spend. Findings feed the live loop.
6. **Control plane** -- H-task queue, consequence gate, memory bank,
   spend tracking, daemon writer exclusivity.

## Quick start

```bash
# Step 1: smoke test (no spend, ~2s)
./scripts/smoke.sh

# Step 2: Muse connectivity (spends ~46 tokens)
./scripts/ask.sh "Reply with exactly: PQ_OK"

# Step 3: full test suite (23 tests, spends on live LLM test)
python3 -m pytest tests/ -v

# Run the live harness (spends budget)
python3 harness.py 5

# Background loop (runs tests continuously)
./scripts/bg.sh
```

## Every run logs

pq's passing criteria: **every run leaves structured logs in `runs/`**.

| Log file | Format | What it records |
|----------|--------|-----------------|
| `runs/runs.jsonl` | JSONL | Structured run result: captures, turns, state, tokens, run_id |
| `runs/usage.jsonl` | JSONL | Per-API-call: tokens, cost, model, duration, run_id |
| `runs/scanner-*.json` | JSON | Deterministic scanner findings per run |
| `runs/smoke-*.jsonl` | JSONL | Smoke test pass/fail per check |
| `runs/llm-runs.jsonl` | JSONL | Live LLM test usage |
| `runs/chaos.jsonl` | JSONL | Chaos battery verdicts |
| `runs/e2e-loop.jsonl` | JSONL | End-to-end test steps |
| `memory/*.md` | Markdown | Cross-run experience bank |
| `memory/bank.jsonl` | JSONL | Memory bank write/remove/freeze events |

Every harness run generates a `run_id` (UTC timestamp) that groups all
log entries for that run. The run result in `runs/runs.jsonl` includes:
state (`ALL_CAPTURED`, `PARTIAL`, `EMPTY_REPLIES`, `TURNS_EXHAUSTED`),
capture list with targets and turn numbers, total tokens, and tools used.

## Relationship to qpbot

```
qpbot/                     pq/
-----------------------    ----------------------------
core/ (arena, ledger,      core/ (same, copied)
  agents, tournament,        + harness.py (live LLM)
  autopilot, guards,         + scripts/ (ask, live, smoke)
  campaign, cli)             + dashboard/ (web UI)
                             + authority/ (Ed25519 grants)
agentcom/ (vault,           + consequence gate
  htasks, lanes,             + vault broker
  daemon, bridge)            + live tests
                             + scanners/ (deterministic recon)
56 unit tests (no LLM)     23 tests (call Muse live)
```

Code flows one direction: **qpbot -> pq**. When qpbot's core changes, pq
picks it up by copying the updated files. pq never edits qpbot.

## Architecture

```
qpbot (source) --copies--> pq (live testing)
                                |
                         harness.py
                                |
                    +-----------+-----------+
                    |  vault (5 LLM keys)   |
                    |  muse-spark-1.3        |
                    |  OpenCode Go API       |
                    +-----------+-----------+
                                |
                    +-----------+-----------+
                    |  arena (3 targets)     |
                    |  via core.cli subprocess|
                    +-----------------------+
                                |
                    runs/runs.jsonl  (structured result)
                    runs/usage.jsonl (per-call usage)
                    memory/          (cross-run experience)
```

## Directory layout

```
pq/
  core/           Arena game engine (copied from qpbot, stdlib only)
  agentcom/       Control plane: vault, authority, htasks, daemon, memory
  harness.py      Live LLM test runner (logs to runs/)
  scripts/        Shell automation (ask, live, smoke, bg, dashboard)
  dashboard/      Web UI (chat + H-task rail + vault deposit)
  scanners/       Deterministic recon (banner, creds, traversal, sqli)
  tests/          Live + offline tests (23 total)
  specs/          Canonical spec tree (reference, not runnable)
  runs/           Runtime output — every run leaves logs here (gitignored)
  memory/         Cross-run experience bank
```

## What's in qpbot (the system under test)

qpbot has 56 unit tests across 7 test files:
- `test_xmrecon.py` (8) -- arena verifier, anti-cheat, receipts, CLI
- `test_autonomous.py` (4) -- tournament ranking, promotion gate, autopilot
- `test_vault.py` (7) -- encrypted store, grants, expiry, usage caps
- `test_classifier.py` (12) -- key type detection, tier assignment
- `test_enforcement.py` (8) -- rate limiter, circuit breaker, async logger
- `test_agentcom.py` (12) -- H-tasks, Seed0, daemon, bridge, ACP
- `test_privacy.py` (4) -- secret never leaks through any channel

pq's 23 tests exercise the live LLM path and the control plane
extensions that qpbot's unit tests don't cover (authority grants,
consequence gate, broker isolation, quarantine/promote, provider
registry, request redaction).

See `AGENTS.md` for deterministic agent onboarding, `DEV_PLAN.md` for
build order, `HANDOVER.md` for full system documentation.
