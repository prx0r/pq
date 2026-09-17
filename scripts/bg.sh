#!/usr/bin/env bash
# bg.sh — background logged test loop. Spend-free (no live model calls).
#   ./scripts/bg.sh start [interval_s]  # default 300; logs runs/bg-*.jsonl
#   ./scripts/bg.sh status
#   ./scripts/bg.sh stop
source "$(dirname "$0")/lib.sh"
need python3; need nohup

PIDF="$RUNS/bg.pid"
INTERVAL="${2:-300}"

is_alive() { [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF")" 2>/dev/null; }

case "${1:-status}" in
  start)
    if is_alive; then echo "bg loop already running pid=$(cat "$PIDF")"; exit 0; fi
    nohup bash "$PQ_ROOT/scripts/bg-loop.sh" "$INTERVAL" >>"$RUNS/bg.out" 2>&1 &
    echo "$!" > "$PIDF"
    echo "bg loop started pid=$! interval=${INTERVAL}s (logs runs/bg-*.jsonl)"
    ;;
  stop)
    if ! is_alive; then echo "bg loop not running"; rm -f "$PIDF"; exit 0; fi
    kill "$(cat "$PIDF")" && rm -f "$PIDF"
    echo "bg loop stopped"
    ;;
  status)
    if is_alive; then
      echo "bg loop alive pid=$(cat "$PIDF")"
      tail -n 3 "$RUNS/bg.jsonl" 2>/dev/null || echo "(no iterations yet)"
    else
      echo "bg loop not running"; rm -f "$PIDF"; exit 1
    fi
    ;;
  *) echo "usage: bg.sh {start [interval_s]|stop|status}" >&2; exit 2;;
esac
