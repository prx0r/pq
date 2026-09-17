# V1 Architecture — LLM-driven scanner core with RSI learning

## The loop

```
┌─────────────────────────────────────────────────────────┐
│                    MEMORY BANK                           │
│  memory/procedures.md  — what worked, what failed       │
│  memory/wordlists/     — learned creds, paths, payloads │
│  memory/findings/      — past discoveries (redacted)    │
│  memory/freezes/       — snapshots for eval             │
└────────────────────────┬────────────────────────────────┘
                         │ preamble injected into prompt
                         ▼
┌─────────────────────────────────────────────────────────┐
│                    LLM (brain)                           │
│  Sees: memory preamble + scanner findings + tool list   │
│  Decides: which tool to fire next, with what args       │
│  Outputs: TOOL: <name> <args>                           │
└────────────────────────┬────────────────────────────────┘
                         │ fire tool
                         ▼
┌─────────────────────────────────────────────────────────┐
│                 TOOL REGISTRY                            │
│  recon:     gh_search, env_scan, git_history            │
│  classify:  drain_classify (what CAN this key do)       │
│  balance:   eth_check, sol_check, batch_check           │
│  derive:    mnemonic_derive                             │
│  capture:   prize_record (vault.store)                  │
└────────────────────────┬────────────────────────────────┘
                         │ structured JSON result
                         ▼
┌─────────────────────────────────────────────────────────┐
│              DRAIN AUTHORITY CLASSIFIER                  │
│  For each finding, determine:                           │
│    class:     DERIVATION_ROOT / ROOT_SIGNER /            │
│                SIGNING_DELEGATE / CUSTODIAL / FP         │
│    chain:     eth / sol / multi / aws / other           │
│    can_drain: bool                                      │
│    actions:   [drain_eth, derive_sol, trade_only, ...]  │
│    priority:  critical / high / medium / low / info     │
│    balance:   {eth, sol, usdc, total_usd}              │
└────────────────────────┬────────────────────────────────┘
                         │ prize if can_drain && balance > 0
                         ▼
┌─────────────────────────────────────────────────────────┐
│              VAULT + PRIZE PIPELINE                      │
│  quarantine discovered secrets (never auto-authorize)   │
│  record prize with: classification, balance, actions    │
│  grow wordlists from successful captures                │
└────────────────────────┬────────────────────────────────┘
                         │ post-run
                         ▼
┌─────────────────────────────────────────────────────────┐
│              RSI LEARNING LOOP                           │
│  1. same-context distill: what worked, what failed      │
│  2. reconcile: remove contradictions                    │
│  3. commit to memory bank + freeze snapshot             │
│  4. next run: memory preamble in prompt                 │
│  5. eval: held-out targets, baseline vs memory arm      │
└─────────────────────────────────────────────────────────┘
```

## What makes this powerful

### 1. Deterministic classifiers behind every LLM decision

The LLM never "decides" what a key is. It fires `classify` or `drain_classify`,
which returns a deterministic JSON verdict:

```json
{
  "class": "ROOT_SIGNER",
  "chain": "eth",
  "can_drain": true,
  "confidence": 0.85,
  "actions": ["drain_eth", "drain_erc20", "swap_to_xmr"],
  "priority": "check_balance"
}
```

The LLM reads this and decides what to do next (check balance, try to capture,
skip it). The classifier is deterministic, testable, and never hallucinates.

### 2. Actions, not just types

Old: "found a private key" → ???  
New: "found ROOT_SIGNER on eth, can_drain=True, actions=[drain_eth, drain_erc20,
swap_to_xmr], priority=check_balance" → clear next step

### 3. Prize = can_drain AND balance > 0

The optimization target isn't "find more keys" — it's:
- Find keys that CAN drain (class = ROOT_SIGNER or DERIVATION_ROOT)
- AND have verified balance (balance > 0 via public RPC)
- AND haven't been captured before

This is a harder, more honest target than just counting finds.

### 4. RSI loop learns from failures

Each run produces:
- What scanner found (findings)
- What classifier said (classifications)
- What balance check showed (balances)
- What was captured (prizes)
- What was false positive (dropped)

The memory bank learns: "env_scan found 5 keys, 4 were false positives
because they were tx hashes in deployment logs. Next time, check context
before firing balance check."

### 5. Held-out evaluation

Two arms:
- **Baseline**: scanners only, no memory
- **Memory**: scanners + memory preamble from previous runs

On held-out planted targets: does memory improve turn count? Capture rate?
False positive reduction? If yes, the loop is learning. If no, memory is
just noise.

## File layout

```
pq/
├── scanners/
│   ├── registry.py           # tool registry (LLM fires tools)
│   ├── drain_classify.py     # drain authority classifier
│   ├── run_all.py            # deterministic scanner runner
│   ├── banner.py             # probe targets
│   ├── creds.py              # default credential spray
│   ├── traversal.py          # path traversal
│   ├── sqli.py               # SQL injection
│   ├── common.py             # shared plumbing
│   └── wordlists/            # learned wordlists (grow from captures)
├── scripts/simulations/
│   ├── gh_secret_scanner.py  # GitHub search for leaked keys
│   ├── eth_check.py          # ETH + ERC-20 balance
│   ├── sol_check.py          # SOL + SPL balance
│   ├── batch_check.py        # parallel balance check
│   ├── mnemonic_derive.py    # BIP-39 derivation
│   ├── env_extract.py        # scan .env files
│   ├── git_history_scan.py   # scan git history
│   └── classify_secret.py    # basic type detection
├── memory/                    # RSI memory bank
│   ├── procedures.md          # learned procedures
│   ├── session-*.md           # per-run distill logs
│   └── freezes/               # frozen snapshots
├── harness.py                 # LLM loop (drives tools)
└── agentcom/
    ├── memory/bank.py         # memory bank module
    └── vault/                 # secret store + prize pipeline
```
