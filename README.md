# pq — autonomous red-team CTF system with vault + usage enforcement

A capture-the-flag arena where autonomous agents play against simulated
targets. Vault-held API keys, deterministic usage tracking, rate limiting,
circuit breaking. Built for Pi workers via ACP, Argos desktop, AgentDeck
phone control.

## Start here (AI agents: ChatGPT, Pi, fresh shells)

No keys, no config, no setup. Every script uses our hardcoded Muse backend
(`muse-spark-1.3-contributor` via OpenCode Go; keys resolve from the vault,
usage is logged). Run from the repo root:

```bash
./scripts/ask.sh "your prompt here"   # one-shot Muse inference, prints reply
./scripts/smoke.sh                    # fast health check, no spend
./scripts/run-all.sh                  # full validation: arena + chaos + autonomy loop
./scripts/live.sh [turns]             # live Muse red-team run (spends budget)
./scripts/dashboard.sh [port]         # 0-9 human-rail transport, loopback only
./scripts/bg.sh {start|status|stop}   # background logged test loop (no spend)
```

`ask.sh` is the primitive: prompt in, Muse reply out, exit non-zero with
`REFUSED:` on spend caps or dead keys. All runs append JSONL evidence under
`runs/` (gitignored). `tests/` holds one rule: a test IS a logged LLM run —
`pytest tests/` calls Muse live.

Backend details (you don't need these to use it): model + endpoint are
pinned in `scripts/lib.sh`; the harness speaks the Responses API at
`https://opencode.ai/zen/go/v1/responses`; vault grants are scoped per
tool/worker with Failover across keys. Do not commit keys — the vault file
lives outside the repo and is never in git.

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

**harness.py** — live test runner. Vault picks a usable key (failover),
calls Muse on OpenCode Go, feeds tool results back, tracks usage. Honors
`PQ_SPEND_CAP_TOKENS` / `PQ_SPEND_CAP_MINOR` (unset = uncapped).

## Run

```bash
./scripts/smoke.sh                       # health check, no spend
./scripts/run-all.sh                     # arena + chaos + autonomy loop
./scripts/live.sh 20                     # live Muse red-team (spends budget)
python3 -m pytest tests/ -q              # the one live LLM test
python3 -m core.cli tournament           # 3 lanes compete
python3 -m core.cli autopilot --rounds 3 # continuous loop
python3 -m core.cli vault-find --kind llm      # usable keys
python3 -m core.cli vault-usage                # spend summary
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
