# pq — autonomous red-team CTF system with vault + usage enforcement

A capture-the-flag arena where autonomous agents play against simulated
targets. Vault-held API keys, deterministic usage tracking, rate limiting,
circuit breaking. Built for Pi workers via ACP, Argos desktop, AgentDeck
phone control.

## What's here

**core/** — the running game. Server-side arena with 3 demo targets,
hash-chained ledger, red-team agent loop, 3-lane tournament, autopilot
with spend caps, promotion gate (min uses, 90% pass, zero regressions).
CLI: `python3 -m core.cli tournament`, `... autopilot`, `... run`.

**agentcom/** — headless control plane. H-task queue with leases + expiry.
Seed0 frozen-root tournament runner. Spend ledger. Daemon with writer
exclusivity + crash-to-UNKNOWN. Pi lane specs. ACP routing. AgentDeck
bridge (tiles + state projection). Vault: encrypted store, scoped grants,
rate limiter, circuit breaker, async usage logger, tracker with provider
pricing.

**connectors/pi-xmrecon/** — Pi SDK integration. Raw chat mode (no tools)
and red-team mode (explicit arena tools via CLI). TypeScript, needs
`npm install` + model key at runtime.

**dashboard/** — stdlib HTTP server. Chat + H-task rail + vault deposit.
Token-gated, binds loopback. Cloudflare tunnel for remote access.

**harness.py** — live test runner. Vault picks active key, calls mimo-v2.5
via OpenCode Go, feeds tool results back, tracks usage.

## Run

```bash
python3 -m pytest tests/ -q                    # 43 tests
python3 -m core.cli tournament                 # 3 lanes compete
python3 -m core.cli autopilot --rounds 3       # continuous loop
python3 -m core.cli vault-find --kind llm      # active keys
python3 -m core.cli vault-usage                # spend summary
python3 harness.py                             # live LLM test
```

## Vault primitives (ported from VoidLLM)

- **Rate limiter**: fixed-window, three-tier most-restrictive-wins
- **Circuit breaker**: three-state, RecordNeutral for 429s
- **Async logger**: buffered, drop-on-full, batch flush to vault + JSONL
- **Tracker**: per-model pricing, deterministic cost_minor calculation

## Architecture

```
YOU
 │
 ├── ARGOS (desktop, ACP)
 ├── AGENTDECK (phone, 0-9)
 │
 ▼
AGENTCOM v2 (control plane)
 │
 ├── ATask → Pi worker (ACP)
 ├── H-task queue → human
 ├── Vault (encrypted, scoped)
 └── QP (truth, settlement)
      │
      ▼
     ARENA (game truth)
```

See `docs/` for full plans, `DEV_PLAN.md` for build order.
