#!/usr/bin/env bash
# lib.sh — shared helpers for pq scripts. Source it, don't run it.
#   source "$(dirname "$0")/lib.sh"
#
# Reads configuration from pq.json at the repo root.
# All env vars can be overridden; pq.json provides defaults.
set -euo pipefail

PQ_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PQ_ROOT
RUNS="$PQ_ROOT/runs"
mkdir -p "$RUNS"

# ── Read defaults from pq.json ────────────────────────────────────────
# Uses python3 to parse JSON (stdlib only, no jq dependency).
_cfg() {
  python3 -c "
import json, os, sys
p = os.path.join('$PQ_ROOT', 'pq.json')
if os.path.exists(p):
    c = json.load(open(p))
    parts = '$1'.split('.')
    n = c
    for k in parts:
        if isinstance(n, dict) and k in n: n = n[k]
        else: sys.exit(1)
    print(n)
" 2>/dev/null || echo "$2"
}

# Backend — override with PQ_MODEL env, defaults to pq.json → llm.model
export PQ_MODEL="${PQ_MODEL:-$(_cfg 'llm.model' 'muse-spark-1.3-contributor')}"
export PQ_API="${PQ_API:-$(_cfg 'llm.base_url' 'https://opencode.ai/zen/go/v1')}"
export PQ_VAULT="${PQ_VAULT:-$(python3 -c "import os; print(os.path.expanduser('$(_cfg vault.path ~/.qpbot/vault.json)'))")}"
export QP_BOT="${QP_BOT:-$(_cfg 'arena.qp_bot' '/home/ubuntu/qpbot')}"

need() {
  command -v "$1" >/dev/null 2>&1 || { echo "missing required command: $1" >&2; exit 2; }
}

# log_event <file> <json-line> — append one JSONL event under runs/
log_event() {
  printf '%s\n' "$2" >> "$RUNS/$1"
}

run_id() {
  date -u +%Y%m%d-%H%M%S
}

# qp_cli <args...> — run qpbot arena CLI (the system under test), print stdout
qp_cli() {
  (cd "$QP_BOT" && python3 -m core.cli "$@" 2>/dev/null)
}
