#!/usr/bin/env bash
# bootstrap.sh — full setup from a fresh clone. One command.
#   ./scripts/bootstrap.sh                      # interactive
#   PQ_API_KEY=sk-xxx ./scripts/bootstrap.sh    # non-interactive
#
# What it does:
#   1. Checks Python + dependencies
#   2. Creates vault at the path in pq.json
#   3. Stores your LLM key in the vault
#   4. Runs smoke test
#   5. Tests Muse connectivity
#   6. Runs the test suite
set -euo pipefail

PQ_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PQ_ROOT"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
step() { echo -e "\n${CYAN}[$1/6]${NC} $2"; }
ok()   { echo -e "  ${GREEN}ok${NC} $1"; }
warn() { echo -e "  ${YELLOW}warn${NC} $1"; }
fail() { echo -e "  ${RED}FAIL${NC} $1"; }

echo -e "${CYAN}=== pq bootstrap ===${NC}"
echo "Config: pq.json"
echo "Vault:  $(python3 -c "import os; print(os.path.expanduser('$(python3 -c "import json; print(json.load(open('pq.json')).get('vault',{}).get('path','~/.qpbot/vault.json'))")'))")"

# Step 1: Python
step 1 "Checking Python..."
python3 --version >/dev/null 2>&1 && ok "python3" || { fail "python3 not found"; exit 1; }
python3 -c "import cryptography" 2>/dev/null && ok "cryptography" || { fail "pip install cryptography"; exit 1; }
python3 -m pytest --version >/dev/null 2>&1 && ok "pytest" || { fail "pip install pytest"; exit 1; }

# Step 2: Vault
step 2 "Setting up vault..."
VAULT=$(python3 -c "import json,os; print(os.path.expanduser(json.load(open('pq.json')).get('vault',{}).get('path','~/.qpbot/vault.json')))" 2>/dev/null)
mkdir -p "$(dirname "$VAULT")"

if [ ! -f "$VAULT" ]; then
  python3 -c "
import sys, os, json; sys.path.insert(0, '.')
from agentcom.vault.store import Vault
v = Vault('$VAULT')
print(f'vault created: $VAULT')
# Store key from env if provided
key = os.environ.get('PQ_API_KEY', '')
if key:
    v.store('LLM_KEY', key,
            ['dashboard-chat', 'pi-redteam', 'harness'],
            ['chat-session', 'lane-1', 'harness-run'],
            kind='llm-inference', tier='paid',
            ttl_s=86400*30, max_uses=0)
    print('key stored as LLM_KEY')
else:
    print('no PQ_API_KEY set — store a key later')
"
  ok "vault created"
else
  ok "vault exists"
fi

# Show key count
KEY_COUNT=$(python3 -c "
import sys; sys.path.insert(0, '.')
from agentcom.vault.store import Vault
v = Vault('$VAULT')
print(len(v.find(kind='llm-inference', tier='paid')))
" 2>/dev/null || echo "0")
ok "LLM keys: $KEY_COUNT"

# Step 3: Store key if env var set and not already in vault
if [ -n "${PQ_API_KEY:-}" ] && [ "$KEY_COUNT" = "0" ]; then
  step 3 "Storing API key..."
  python3 -c "
import sys; sys.path.insert(0, '.')
from agentcom.vault.store import Vault
v = Vault('$VAULT')
v.store('LLM_KEY', '$PQ_API_KEY',
        ['dashboard-chat', 'pi-redteam', 'harness'],
        ['chat-session', 'lane-1', 'harness-run'],
        kind='llm-inference', tier='paid', ttl_s=86400*30, max_uses=0)
print('key stored')
"
  ok "API key stored"
else
  step 3 "API key..."
  if [ "$KEY_COUNT" != "0" ]; then
    ok "keys already present, skipping"
  else
    warn "no PQ_API_KEY env var — set it or store manually later"
  fi
fi

# Step 4: Smoke test
step 4 "Running smoke test..."
if python3 -c "
import sys; sys.path.insert(0, '.')
import harness, dashboard.server
from agentcom.htasks.queue import HQueue
from scanners.registry import tool_names
print(f'{len(tool_names())} tools registered')
" 2>/dev/null; then
  ok "imports + tools"
else
  fail "imports failed"
fi

# Step 5: Muse connectivity
step 5 "Testing Muse connectivity..."
if [ "$KEY_COUNT" != "0" ]; then
  RESULT=$(timeout 30 python3 -c "
import sys, json, urllib.request, uuid; sys.path.insert(0, '.')
import pqconfig as cfg
from agentcom.vault.store import Vault
v = Vault(cfg.vault_path())
active = v.find(kind='llm-inference', tier='paid')
if not active:
    print('no active keys'); sys.exit(1)
c = active[0]
try:
    key = v.resolve(c['name'], 'dashboard-chat', 'chat-session', c['capability'])
except Exception as e:
    print(f'resolve failed: {e}'); sys.exit(1)
body = json.dumps({'model': cfg.llm_model(),
                  'input': [{'role': 'user', 'content': 'Reply with exactly: PQ_OK'}],
                  'stream': False, 'max_output_tokens': 1024}).encode()
req = urllib.request.Request(cfg.llm_base_url().rstrip('/') + '/responses',
                           data=body,
                           headers={'Content-Type': 'application/json',
                                   'Authorization': f'Bearer {key}',
                                   'x-opencode-session': str(uuid.uuid4())},
                           method='POST')
with urllib.request.urlopen(req, timeout=20) as r:
    resp = json.loads(r.read())
for item in resp.get('output', []):
    for ct in item.get('content', []):
        if ct.get('type') == 'output_text' and 'PQ_OK' in ct.get('text', ''):
            print('ok'); sys.exit(0)
print('no PQ_OK in response'); sys.exit(1)
" 2>/dev/null) || true
  if [ "$RESULT" = "ok" ]; then
    ok "Muse responded with PQ_OK"
  else
    warn "Muse test failed or timed out (may be transient)"
  fi
else
  warn "skipping (no keys in vault)"
fi

# Step 6: Test suite
step 6 "Running test suite..."
TEST_OUT=$(python3 -m pytest tests/ -q 2>&1)
PASS=$(echo "$TEST_OUT" | grep -oP '\d+ passed' | head -1)
SKIP=$(echo "$TEST_OUT" | grep -oP '\d+ skipped' | head -1)
ok "${PASS:-0} passed, ${SKIP:-0} skipped"

# Summary
echo -e "\n${CYAN}=== bootstrap complete ===${NC}"
echo
echo "Dashboard:  ./scripts/dashboard.sh              (chat with LLM)"
echo "Live game:  ./scripts/live.sh 5                 (spends budget)"
echo "One-shot:   ./scripts/ask.sh 'hello'            (spends ~46 tokens)"
echo "Tests:      python3 -m pytest tests/ -v         (150 tests)"
echo "Config:     pq.json                             (change model, vault, etc)"
