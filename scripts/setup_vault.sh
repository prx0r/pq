#!/usr/bin/env bash
# setup_vault.sh — create and populate the vault with an LLM key.
#   ./scripts/setup_vault.sh                    # interactive
#   PQ_API_KEY=sk-xxx ./scripts/setup_vault.sh  # non-interactive
set -euo pipefail

PQ_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VAULT_DIR="$HOME/.qpbot"
VAULT="$VAULT_DIR/vault.json"

mkdir -p "$VAULT_DIR"

if [ -f "$VAULT" ]; then
  echo "Vault already exists: $VAULT"
  echo "To re-create, delete it first: rm $VAULT"
  exit 0
fi

echo "Creating vault..."
cd "$PQ_ROOT"

python3 -c "
import os, sys
sys.path.insert(0, '$PQ_ROOT')
from agentcom.vault.store import Vault

vault_path = os.path.expanduser('~/.qpbot/vault.json')
v = Vault(vault_path)
print(f'Vault created: {vault_path}')

# Store the API key if provided via env
key = os.environ.get('PQ_API_KEY', '')
if key:
    result = v.store('LLM_KEY', key,
                     ['dashboard-chat', 'pi-redteam', 'harness'],
                     ['chat-session', 'lane-1', 'harness-run'],
                     kind='llm-inference', tier='paid',
                     ttl_s=86400*30, max_uses=0)
    print(f'Key stored as LLM_KEY (expires in 30 days, unlimited uses)')
else:
    print('No PQ_API_KEY set. Store a key later via:')
    print('  printf \"your-key\" | python3 -m core.cli vault-store LLM_KEY \\\\')
    print('    --tools dashboard-chat,harness --workers chat-session,harness-run')
    print('  Or use the dashboard: ./scripts/dashboard.sh')
"
