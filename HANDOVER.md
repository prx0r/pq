# HANDOVER — welcome to pq

This document explains the entire system to a fresh agent. Read this first.

## What is pq

An autonomous red-team CTF system. Agents find targets, extract secrets,
chain receipts. Vault stores keys. Usage is tracked. Rate limits and circuit
breakers prevent burn. Everything is modular and testable.

## Where things live

```
pq/
├── core/              The running game (Python, stdlib only)
│   ├── arena.py       3 demo targets, server-side verifier
│   ├── ledger.py      hash-chained event store
│   ├── agents.py      red-team loop (perceive → act → verify)
│   ├── tournament.py  3 strategy lanes compete
│   ├── autopilot.py   continuous loop with spend caps
│   ├── guards.py      promotion gate + budget caps
│   ├── cli.py         CLI surface (17 verbs)
│   └── module_adapter.py  status feed for controllers
│
├── agentcom/          Control plane (Python)
│   ├── vault/         encrypted store + enforcement
│   │   ├── store.py   secrets, grants, prizes, captures
│   │   ├── classifier.py  detect key type + assign tier
│   │   ├── scripts.py     tier-specific runners
│   │   ├── ratelimit.py   three-tier rate limiter
│   │   ├── circuitbreaker.py  three-state breaker
│   │   ├── asynclog.py    buffered usage logger
│   │   └── tracker.py     per-model pricing
│   ├── htasks/        human work queue
│   ├── lanes/         Seed0 frozen-root runner
│   ├── ledger/        spend tracking
│   ├── services/      daemon (writer exclusivity)
│   ├── interfaces/    ACP routing + AgentDeck bridge
│   └── runtime/       Pi lane specs
│
├── connectors/        Pi SDK integration (TypeScript)
├── dashboard/         web UI (chat + H-task rail)
├── harness.py         live LLM test runner
├── scripts/           shell scripts for automation
├── tests/             56 tests
├── specs/             full canonical tree (QP, processors, contracts)
├── docs/              architecture, playbook, privacy
└── planted-repos/     test targets (local, not in git)
```

## Quick start

```bash
python3 -m pytest tests/ -q                    # 56 tests, no keys needed
python3 -m core.cli tournament                 # 3 lanes compete
python3 -m core.cli autopilot --rounds 3       # continuous loop
python3 -m core.cli vault-find --kind llm      # active keys
python3 -m core.cli vault-usage                # spend summary
python3 -m core.cli prize                      # captured assets
```

## How the vault works

1. **Store a key**: `printf 'key' | python3 -m core.cli vault-store NAME --tools tool1 --workers w1`
2. **Find keys**: `python3 -m core.cli vault-find --kind llm-inference`
3. **Resolve**: vault.decrypt(name, tool, worker, capability) → plaintext
4. **Capture**: agent finds secret → classifier detects type → tier scripts run → stored as asset
5. **Track**: every API call logs tokens + cost to vault usage

## How the prize system works

When an agent captures a target:
1. `vault.capture()` records the prize (who, what, when, cost)
2. If a secret was found, `classifier.py` detects the type
3. `scripts.py` runs tier-specific analysis (balance checks, permission enum, etc.)
4. The secret is stored as a named vault asset with metadata
5. Next agent can `vault-find` and use it

Tiers:
- Tier 1 (crypto): balance, derive address, token holdings
- Tier 2 (cloud/API): permissions, scopes, rate limits
- Tier 3 (credential): mnemonic validation, breach check
- Tier 4 (generic): service identification

## How the arena works

3 demo targets with server-side verification:
- weak-creds-01: try admin/admin
- traversal-01: try ../../flag.txt
- sqli-sim-01: try ' OR '1'='1

Every claim settles through `arena.submit_flag()`. Hash comparison only.
Receipts chain in the ledger. Verification is deterministic.

## How testing works

- `tests/test_xmrecon.py`: arena verifier, anti-cheat, receipt verify
- `tests/test_autonomous.py`: tournament ranking, promotion gate, autopilot
- `tests/test_vault.py`: store, resolve, expiry, usage caps, find
- `tests/test_enforcement.py`: rate limiter, circuit breaker, async logger
- `tests/test_privacy.py`: secret never leaks through any channel
- `tests/test_agentcom.py`: H-tasks, Seed0, daemon, bridge, ACP
- `tests/test_classifier.py`: key type detection, tier assignment, scripts

## What's in specs/

The full canonical QP system: truth core (northstar + acom kernel),
processor SDK with 5 lanes, control v07 runtime, 5 contracts, adapters,
autobuild compiler, trajectory store, HLoop, validation labs. An external
agent can read `specs/qp/NORTHSTAR.md` for the thesis and
`specs/processors/QP_PROCESSOR.md` for the formal definitions.

## Key files to read

1. `README.md` — project overview
2. `docs/PLAY.md` — every runnable command
3. `docs/STACK.md` — how pieces connect
4. `docs/PRIVACY.md` — what cannot leak
5. `DEV_PLAN.md` — build order with file provenance
6. `specs/INSANE.md` — security findings from zip analysis
7. `agentcom/vault/classifier.py` — how keys are classified
8. `agentcom/vault/store.py` — the vault itself

## Rules

1. Keys via env at runtime, never repo or chat
2. Vault file never committed (.gitignore blocks it)
3. Verifier behavior changes need a new test contract
4. High-risk tools deny by default (fail closed)
5. Captured secrets auto-classify and store as assets
6. Every capture records a prize with full metadata
