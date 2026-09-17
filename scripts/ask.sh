#!/usr/bin/env bash
# ask.sh — one-shot inference on OUR hardcoded Muse backend.
# Any agent (ChatGPT, Pi, fresh shell) runs this; no keys, no config needed.
#   ./scripts/ask.sh "Reply with exactly: PQ_OK"
#   ./scripts/ask.sh "Explain Raft in 3 bullets" > answer.txt
# Spends budget (one call). Honors PQ_SPEND_CAP_TOKENS/_MINOR. Logs to runs/.
source "$(dirname "$0")/lib.sh"
need python3
[ $# -ge 1 ] || { echo "usage: ask.sh \"prompt\"" >&2; exit 2; }
cd "$PQ_ROOT"
python3 - "$@" <<'EOF'
import sys, os, time, urllib.error
sys.path.insert(0, os.environ['PQ_ROOT'])
import pqconfig as cfg
from agentcom.vault.store import Vault
from agentcom.vault.tracker import cost_minor
from agentcom.vault.asynclog import UsageLogger
from harness import call_api, _spend_ok

prompt = sys.argv[1]
model = cfg.llm_model()
vault = Vault(cfg.vault_path())
if not _spend_ok(vault):
    print('REFUSED: spend cap reached', file=sys.stderr); sys.exit(3)
cands = sorted(vault.find(kind='llm-inference', tier='paid'),
               key=lambda a: 0 if a.get('model') == model else 1)
key = pick = None
for c in cands:
    try:
        key = vault.resolve(c['name'], 'dashboard-chat', 'chat-session',
                            c['capability'])
        pick = c
        break
    except ValueError:
        continue
if key is None:
    print('REFUSED: no usable LLM keys (all spent/expired)', file=sys.stderr)
    sys.exit(3)
t0 = time.time()
try:
    resp = call_api(key, [{'role': 'user', 'content': prompt}], model=model)
except urllib.error.HTTPError as e:
    print(f'BACKEND ERROR: HTTP {e.code} {e.read().decode()[:200]}',
          file=sys.stderr)
    sys.exit(1)
ms = int((time.time() - t0) * 1000)
u = resp.get('usage', {})
ti, to = u.get('prompt_tokens', 0), u.get('completion_tokens', 0)
text = (resp['choices'][0]['message']['content'] or '')
lg = UsageLogger(vault=vault,
                 log_path=os.path.join(cfg.runs_dir(), 'llm-runs.jsonl'),
                 buffer_size=100, flush_interval_s=1)
lg.log(pick['name'], resp.get('model', model), tokens_in=ti, tokens_out=to,
       cost_minor=cost_minor(model, ti, to), duration_ms=ms)
lg.shutdown()
print(text)
EOF
