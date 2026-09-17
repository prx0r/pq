#!/usr/bin/env bash
# bg-loop.sh — one deterministic validation pass every INTERVAL seconds.
# Started via bg.sh start (nohup). Single instance via lock dir.
set -euo pipefail
PQ_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
QP_BOT="${QP_BOT:-/home/ubuntu/qpbot}"
RUNS="$PQ_ROOT/runs"
INTERVAL="${1:-300}"
LOCK="$RUNS/.bg-lock"

if ! mkdir "$LOCK" 2>/dev/null; then
  echo "bg-loop: another instance holds $LOCK, exiting" >&2
  exit 1
fi
trap 'rm -rf "$LOCK"' EXIT
echo "bg-loop: up interval=${INTERVAL}s (pid $$)"

while true; do
  ts="$(date -u +%Y%m%d-%H%M%S)"
  detail="$RUNS/bg-$ts.jsonl"
  {
    echo "== bg pass $ts =="
    pytest_line=$(cd "$QP_BOT" && python3 -m pytest tests/ -q -p no:cacheprovider 2>&1 | tail -n 1)
    echo "qpbot-suite: $pytest_line"
    (cd "$QP_BOT" && python3 -m core.cli tournament 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin)
lanes={k:v.get('captured') for k,v in d.get('lanes',{}).items()}
print('tournament:',lanes)")
    python3 "$PQ_ROOT/scripts/chaos_battery.py" --quiet 2>&1 | tail -n 1
  } >"$detail" 2>&1 && ok=true || ok=false
  qpbot_failed=$(grep -o '[0-9]* failed' "$detail" | head -n 1 | grep -o '[0-9]*' || echo 0)
  printf '{"ts":"%s","pass":%s,"qpbot_failed":%s,"detail_file":%s}\n' \
    "$ts" "$ok" "${qpbot_failed:-0}" "$(basename "$detail")" >>"$RUNS/bg.jsonl"
  # rotate: keep newest 50 detail logs
  ls -t "$RUNS"/bg-20*.jsonl 2>/dev/null | tail -n +51 | xargs -r rm -f
  sleep "$INTERVAL"
done
