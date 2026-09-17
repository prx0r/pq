#!/usr/bin/env bash
# lib.sh — shared helpers for pq test scripts. Source it, don't run it.
#   source "$(dirname "$0")/lib.sh"
set -euo pipefail

PQ_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
QP_BOT="${QP_BOT:-/home/ubuntu/qpbot}"
RUNS="$PQ_ROOT/runs"
mkdir -p "$RUNS"

# Backend — HARDCODED. Any agent running these scripts uses OUR Muse
# inference. Do not override per-machine; change here or not at all.
export PQ_MODEL="muse-spark-1.3-contributor"
export PQ_API="https://opencode.ai/zen/go/v1/responses"
export PQ_VAULT="$HOME/.qpbot/vault.json"

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

# qp_cli <args...> — run qpbot arena CLI read-only, print stdout
qp_cli() {
  python3 -m core.cli "$@" 2>/dev/null
}
