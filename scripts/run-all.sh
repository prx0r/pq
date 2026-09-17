#!/usr/bin/env bash
# run-all.sh — full validation pass. Spend-free except the e2e human-press
# demo (no model calls). Logs runs/run-all-<ts>.jsonl.
#   ./scripts/run-all.sh
source "$(dirname "$0")/lib.sh"
need python3
cd "$PQ_ROOT"
rid="run-all-$(run_id)"
{
  echo "== $rid: deterministic barrage =="
  python3 - "$QP_BOT" <<'EOF'
import json, subprocess, sys
QP = sys.argv[1]
def cli(*a):
    import subprocess as sp
    p = sp.run([sys.executable, '-m', 'core.cli', *a],
               capture_output=True, text=True, cwd=QP)
    try: return p.returncode, json.loads(p.stdout) if p.stdout.strip() else {}
    except Exception: return p.returncode, {}
ok = 0; n = 0
for job in [('tournament',), ('autopilot', '--rounds', '3'),
            ('run', '--agent', 'red-01', '--pack', 'demo'), ('status',)]:
    rc, d = cli(*job); n += 1; ok += (rc == 0)
    print(' ', job[0], 'rc=', rc)
for store in ['runs/demo/tournament-creds-first/events.jsonl',
              'runs/demo/campaign/events.jsonl']:
    rc, d = cli('chain', store); n += 1; ok += (rc == 0)
    print('  chain', store.split('/')[1], rc)
print('barrage:', ok, '/', n)
EOF
  echo "== $rid: chaos battery =="
  python3 "$PQ_ROOT/scripts/chaos_battery.py" --quiet
  echo "== $rid: e2e autonomy loop =="
  python3 "$PQ_ROOT/scripts/e2e_loop.py" 2>&1 | tail -n 7
} 2>&1 | tee "$RUNS/$rid.log"
echo "logged: runs/$rid.log"
