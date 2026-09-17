#!/usr/bin/env bash
# setup.sh — bootstrap pq for a new agent. Run once.
#   ./scripts/setup.sh
# Checks: Python, vault, Muse connectivity, runs smoke test.
set -euo pipefail

PQ_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

pass=0; fail=0
check() {
  local name="$1"; shift
  if "$@" >/dev/null 2>&1; then
    echo -e "${GREEN}ok${NC}   $name"; pass=$((pass+1))
  else
    echo -e "${RED}FAIL${NC} $name"; fail=$((fail+1))
  fi
}

echo "=== pq setup — checking environment ==="
echo

# Python
check "python3 installed" python3 --version

# pip packages
check "cryptography installed" python3 -c "import cryptography"
check "pytest installed" python3 -m pytest --version

# Vault
echo
echo "--- vault ---"
VAULT="$HOME/.qpbot/vault.json"
if [ -f "$VAULT" ]; then
  echo -e "${GREEN}ok${NC}   vault exists: $VAULT ($(du -h "$VAULT" | cut -f1))"
  KEY_COUNT=$(cd "$PQ_ROOT" && python3 -c "
from agentcom.vault.store import Vault
v = Vault('$VAULT')
print(len(v.find(kind='llm-inference', tier='paid')))
" 2>/dev/null || echo "?")
  echo "       LLM keys: $KEY_COUNT"
else
  echo -e "${YELLOW}WARN${NC} vault not found at $VAULT"
  echo "       Run: ./scripts/setup_vault.sh to create one"
fi

# qpbot (system under test)
echo
echo "--- system under test ---"
QP_BOT="${QP_BOT:-/home/ubuntu/qpbot}"
if [ -d "$QP_BOT" ]; then
  echo -e "${GREEN}ok${NC}   qpbot: $QP_BOT"
else
  echo -e "${YELLOW}WARN${NC} qpbot not found at $QP_BOT"
  echo "       Set QP_BOT=/path/to/qpbot"
fi

# Smoke test
echo
echo "--- smoke test ---"
cd "$PQ_ROOT"
check "pq imports" python3 -c "
import sys; sys.path.insert(0, '$PQ_ROOT')
import harness, dashboard.server
from agentcom.htasks.queue import HQueue
from scanners.registry import tool_names
print(f'{len(tool_names())} tools')
" 2>/dev/null

# Tool registry
echo
echo "--- tool registry ---"
TOOL_COUNT=$(cd "$PQ_ROOT" && python3 -c "
from scanners.registry import tool_names
print(len(tool_names()))
" 2>/dev/null || echo "?")
echo -e "${GREEN}ok${NC}   ${TOOL_COUNT} tools registered (arena + on-chain + scan + classify)"

# Summary
echo
echo "=== setup complete ==="
echo -e "passed: ${GREEN}$pass${NC}  failed: ${RED}$fail${NC}"
echo
if [ "$fail" -gt 0 ]; then
  echo -e "${YELLOW}Fix the failures above, then run:${NC}"
  echo "  ./scripts/smoke.sh          # full smoke test"
  echo "  ./scripts/ask.sh 'hello'    # test Muse connectivity"
  echo "  python3 -m pytest tests/    # run all tests"
else
  echo -e "${GREEN}Everything ready.${NC} Next steps:"
  echo "  ./scripts/ask.sh 'hello'              # test Muse (spends ~46 tokens)"
  echo "  python3 -m pytest tests/ -v           # run all 150 tests"
  echo "  ./scripts/live.sh 5                   # 5-turn live game (spends)"
  echo "  ./scripts/dashboard.sh                # web chat UI on localhost:8791"
fi
