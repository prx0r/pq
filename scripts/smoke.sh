#!/usr/bin/env bash
# smoke.sh — fast health check for fresh agents. No spend, no repo writes
# outside /tmp. Exits non-zero on first failure. Logs result to runs/.
#   ./scripts/smoke.sh
source "$(dirname "$0")/lib.sh"
need python3

RUN_ID="$(date -u +%Y%m%d-%H%M%S)"
SMOKE_LOG="$RUNS/smoke-${RUN_ID}.jsonl"
fail=0
checks=0
passed=0

check() { # <name> <command...>
  local name="$1"; shift
  checks=$((checks + 1))
  if "$@" >/dev/null 2>&1; then
    echo "ok   $name"
    log_event "smoke-${RUN_ID}.jsonl" \
      "{\"ts\":$(date +%s),\"run_id\":\"$RUN_ID\",\"check\":\"$name\",\"pass\":true}"
    passed=$((passed + 1))
  else
    echo "FAIL $name"
    log_event "smoke-${RUN_ID}.jsonl" \
      "{\"ts\":$(date +%s),\"run_id\":\"$RUN_ID\",\"check\":\"$name\",\"pass\":false}"
    fail=1
  fi
}

check "pq imports" python3 -c "
import sys; sys.path.insert(0, '$PQ_ROOT')
import harness, dashboard.server
from agentcom.htasks.queue import HQueue
from agentcom.hloop.decisions import calibration
from agentcom.ledger.spend import SpendLedger
from agentcom.services.daemon import Daemon"

check "qpbot CLI status" bash -c "cd \"$QP_BOT\" && python3 -m core.cli status"

# qpbot is another agent's live tree: report its suite, never gate on it.
echo "-- qpbot suite (informational; their tree moves) --"
(cd "$QP_BOT" && python3 -m pytest tests/ -q -p no:cacheprovider 2>&1 | tail -n 2) || true

python3 - "$PQ_ROOT" <<'EOF'
import sys, tempfile, os
sys.path.insert(0, sys.argv[1])
from agentcom.htasks.queue import HQueue, HTask
from agentcom.ledger.spend import SpendLedger
from agentcom.services.daemon import Daemon
d = tempfile.mkdtemp()
q = HQueue(); t = q.emit(HTask('s', 'digit', 'Q?', prediction='7')); t.display(); t.acknowledge()
t.answer_task('7', '7'); q.save(os.path.join(d, 'q.json'))
assert HQueue.load(os.path.join(d, 'q.json')).tasks['s'].state == 'answered'
s = SpendLedger(); s.record('demo', 'lane', 1, 1, 5)
assert not s.check_cap(5, 'demo')['ok'] and s.check_cap(6, 'demo')['ok']
x = Daemon(); x.submit({}); x.tick(lambda j: 1 / 0)
assert x.queue[-1]['state'] == 'UNKNOWN'
print('ok   stack checks (queue/spend/daemon)')
EOF

# Log summary.
log_event "smoke-${RUN_ID}.jsonl" \
  "{\"ts\":$(date +%s),\"run_id\":\"$RUN_ID\",\"event\":\"summary\",\"checks\":$checks,\"passed\":$passed,\"fail\":$fail}"

[ "$fail" = 0 ] || exit 1
echo "smoke: ALL GREEN"
