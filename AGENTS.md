# AGENTS.md — blueteamer live experiments

## What this repo is

pq is blueteamer's live testing suite for qpbot. It runs a real LLM
(mimo-v2.5 via OpenCode Go) against qpbot's simulated CTF arena and
on-chain discovery tools, then logs every result to `runs/`. Every
finding gets a QP receipt. Nothing is trusted — everything is verified.

The passing criteria is: all tests run, all results logged, all claims
receipted. There is no offline mock mode.

Code flows one direction: **qpbot -> pq**. pq never edits qpbot.

## Your role

You are a blueteamer agent. You test our systems against real APIs.
Everything you do is:
- Logged to runs/ (JSONL, timestamped)
- Validated with QP proofs (receipts)
- Audited (every mutation traced)

You never trust — you prove.

## Quick start (new agent)

```bash
cd /home/ubuntu/pq

# Step 1: bootstrap environment
./scripts/setup.sh

# Step 2: test Muse connectivity (spends ~46 tokens)
./scripts/ask.sh "Reply with exactly: PQ_OK"

# Step 3: run all tests (23 offline + 1 live LLM + 23 on-chain = 150 total)
python3 -m pytest tests/ -v

# Step 4: talk to the LLM via dashboard
./scripts/dashboard.sh
# Opens at http://localhost:8791?token=<printed-token>

# Step 5: run the live game
./scripts/live.sh 5   # 5 turns, spends budget
```

## Vault: where keys live

Vault at `~/.qpbot/vault.json`. Encrypted with Fernet. 5 LLM keys
pre-loaded (`LLM_KEY` through `LLM_KEY_5`).

### List keys
```bash
cd /home/ubuntu/qpbot
python3 -m core.cli vault-find --kind llm-inference --tier paid
python3 -m core.cli vault-usage
```

### Store a new key
```bash
# From CLI
printf 'your-api-key' | python3 -m core.cli vault-store MY_KEY \
  --tools dashboard-chat,harness \
  --workers chat-session,harness-run

# From env (non-interactive)
PQ_API_KEY=sk-xxx ./scripts/setup_vault.sh
```

### Change the LLM backend

The vault stores keys, not model configs. The model is set in two places:

**1. For the harness + scripts (default: muse-spark-1.3-contributor):**
```bash
# Edit scripts/lib.sh line 14:
export PQ_MODEL="muse-spark-1.3-contributor"

# Or override at runtime:
PQ_MODEL="mimo-v2.5" ./scripts/live.sh 5
```

**2. For the dashboard (configurable via UI):**
```bash
# The dashboard stores provider config in runs/provider.json
# Default: muse-spark-1.3-contributor on opencode.ai/zen/go/v1
# Change via the dashboard UI or:
curl -X POST "http://localhost:8791/api/provider?token=TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"base_url":"https://opencode.ai/zen/go/v1","model":"mimo-v2.5"}'
```

**Available models:**
- `muse-spark-1.3-contributor` (default, cheapest, good for testing)
- `mimo-v2.5` (stronger reasoning)
- `mimo-v2.5-pro` (highest quality, most expensive)
- `deepseek-v4-flash`, `deepseek-v4-pro`
- `glm-5.3-flash`, `qwen3.7-plus`, `kimi-k2.6`

**Spend caps:**
```bash
PQ_SPEND_CAP_TOKENS=500 ./scripts/live.sh 10   # stop after 500 tokens
PQ_SPEND_CAP_MINOR=100 ./scripts/live.sh 10    # stop after $1.00
```

## Dashboard

Chat with the LLM through a web UI. Also handles H-task rail and
vault key deposits.

```bash
./scripts/dashboard.sh              # localhost:8791, token printed
./scripts/dashboard.sh 9000         # custom port
```

The dashboard:
- **Chat panel** (left): talk to the LLM, powered by vault-held keys
- **H-task rail** (right): approve/reject pending decisions
- **Provider config** (bottom right): change model + base URL
- **Key deposit** (bottom right): paste API keys into vault

## All scripts

| Script | What it does | Spends? |
|--------|-------------|---------|
| `setup.sh` | Bootstrap environment, check everything | No |
| `setup_vault.sh` | Create vault + store initial key | No |
| `smoke.sh` | Health check (imports, CLI, primitives) | No |
| `ask.sh "prompt"` | One-shot Muse query | Yes |
| `live.sh [turns]` | Multi-turn red-team game | Yes |
| `dashboard.sh [port]` | Web chat UI | On chat |
| `bg.sh` | Background deterministic validation loop | No |
| `run-all.sh` | Full validation pass | No |

## Tool registry

13 tools available to the LLM via `TOOL: <name> <args>`:

**Arena tools** (execute against qpbot):
- `probe`, `try-creds`, `read-file`, `sqli`, `submit`

**On-chain discovery tools** (no signup needed):
- `whale_feed [min_usd]` — large BTC/ETH transactions
- `fomo_leaderboard leaderboard` — top traders from fomo.family
- `fomo_leaderboard lookup <handle>` — resolve trader to wallet
- `eth_check <address>` — ETH + ERC-20 balance (free RPC)
- `sol_check <address>` — SOL + SPL balance (free RPC)

**GitHub tools** (GH_TOKEN optional):
- `wallet_github address <addr>` — search GitHub for wallet address
- `wallet_github keys <type>` — search for leaked keys

**Scan tools** (local, no network):
- `clone_scan <repo_url_or_path>` — clone + scan for secrets
- `env_scan <dir>` — scan directory for .env files
- `git_history <dir>` — scan git history for secrets

**Classification tools**:
- `classify <secret>` — detect key type + tier
- `drain_classify <secret>` — drain authority + actions

Test any tool directly:
```python
from scanners.registry import fire
result = fire("eth_check", ["0x28c6c06298d514db089934071355e5743bf21d60"])
print(result)
```

## Directory layout

```
pq/
  core/               Arena game engine (copied from qpbot)
  agentcom/           Control plane: vault, authority, htasks, daemon
  harness.py          Live LLM test runner (logs to runs/)
  scanners/           Deterministic recon + tool registry
  scripts/            Shell automation + on-chain tools
  dashboard/          Web chat UI
  tests/              150 tests (offline + live + on-chain)
  specs/              Canonical spec tree
  runs/               Runtime output (gitignored)
  memory/             Cross-run experience bank
```

## Key files

| File | Role |
|------|------|
| `harness.py` | Live test runner: vault, Muse, tools, logging |
| `core/arena.py` | 3 demo targets, server-side flag verifier |
| `core/cli.py` | 17-verb CLI for arena and vault operations |
| `scanners/registry.py` | Tool registry (15 tools) |
| `scanners/wordlists/` | Learning wordlists (creds, paths, payloads) |
| `agentcom/vault/store.py` | Encrypted vault with scoped grants |
| `agentcom/vault/asynclog.py` | Buffered usage logger |
| `agentcom/htasks/queue.py` | Human task queue |
| `agentcom/memory/bank.py` | Cross-run experience bank |
| `scripts/lib.sh` | Shared env: PQ_ROOT, QP_BOT, PQ_MODEL |
| `dashboard/server.py` | Web UI server (chat + H-task + vault) |

## What gets logged

Every run leaves traces in `runs/`:

| File | Format | Content |
|------|--------|---------|
| `runs/runs.jsonl` | JSONL | Run result: state, captures, turns, tokens, run_id |
| `runs/usage.jsonl` | JSONL | Per-API-call: tokens, cost, model, duration, run_id |
| `runs/scanner-*.json` | JSON | Scanner findings per run |
| `runs/smoke-*.jsonl` | JSONL | Smoke check pass/fail |
| `runs/llm-runs.jsonl` | JSONL | Live test usage |
| `memory/*.md` | Markdown | Cross-run experience notes |
| `memory/bank.jsonl` | JSONL | Memory bank events |

## Rules for agents

1. **Validate before building.** Run `setup.sh`, then `smoke.sh`, then
   `ask.sh`, then `pytest`. Do not skip steps.
2. **Never commit secrets.** Vault file and key are gitignored.
3. **Code flows qpbot -> pq.** Edit qpbot, copy changed files here.
4. **Tests must log.** Every test run writes to `runs/`.
5. **Spend is real.** Use `PQ_SPEND_CAP_TOKENS` to cap budget.
6. **Backend is hardcoded.** Model is `muse-spark-1.3-contributor`.
   Change in `scripts/lib.sh` or via dashboard UI.
7. **On-chain tools are free.** whale_feed, eth_check, sol_check,
   fomo_leaderboard need no API keys. Use them freely.
8. **GitHub tools are optional.** Set `GH_TOKEN` env var for higher
   rate limits on wallet_github and gh_search.

## The game loop

The v1 loop chains on-chain discovery with secret extraction:

```
whale_feed → find large tx → get wallet address
    ↓
eth_check / sol_check → check if wallet has value
    ↓
wallet_github address <wallet> → search GitHub for leaked keys
    ↓
clone_scan <repo> → git clone + scan for secrets
    ↓
classify / drain_classify → what can this key do?
    ↓
vault.store() → store the finding
    ↓
_update_memory() → learn patterns for next run
```

The LLM drives this loop. Each tool call is logged. The memory bank
accumulates experience across runs. Wordlists grow from captures.
